# -*- coding: utf-8 -*-
import base64
import filecmp
import hashlib
import io
import logging
import os
import re
import shutil
import stat
import struct
import sys
import tarfile
import tempfile
from collections import defaultdict
from subprocess import PIPE
from subprocess import Popen

from exodus_bundler.dependency_detection import detect_dependencies
from exodus_bundler.errors import DependencyDetectionError
from exodus_bundler.errors import InvalidElfBinaryError
from exodus_bundler.errors import MissingFileError
from exodus_bundler.errors import UnexpectedDirectoryError
from exodus_bundler.errors import UnsupportedArchitectureError
from exodus_bundler.launchers import CompilerNotFoundError
from exodus_bundler.launchers import construct_bash_launcher
from exodus_bundler.launchers import construct_binary_launcher
from exodus_bundler.templating import render_template
from exodus_bundler.templating import render_template_file


logger = logging.getLogger(__name__)


def bytes_to_int(bytes, byteorder='big'):
    """Simple helper function to convert byte strings into integers."""
    endian = {'big': '>', 'little': '<'}[byteorder]
    chars = struct.unpack(endian + ('B' * len(bytes)), bytes)
    if byteorder == 'big':
        chars = chars[::-1]
    return sum(int(char) * 256 ** i for (i, char) in enumerate(chars))


def create_bundle(executables, output, tarball=False, rename=[], chroot=None, add=[],
                  no_symlink=[], shell_launchers=False, detect=False):
    """Handles the creation of the full bundle."""
    # Initialize these ahead of time so they're always available for error handling.
    output_filename, output_file, root_directory = None, None, None
    try:

        # Create a temporary unpackaged bundle for the executables.
        root_directory = create_unpackaged_bundle(
            executables, rename=rename, chroot=chroot, add=add, no_symlink=no_symlink,
            shell_launchers=shell_launchers, detect=detect,
        )

        # Populate the filename template.
        output_filename = render_template(output,
            executables=('-'.join(os.path.basename(executable) for executable in executables)),
            extension=('tgz' if tarball else 'sh'),
        )

        # Store a gzipped tarball of the bundle in memory.
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w:gz') as tar:
            tar.add(root_directory, arcname='exodus')

        # Configure the appropriate output mechanism.
        if output_filename == '-':
            output_file = getattr(sys.stdout, 'buffer', sys.stdout)
        else:
            output_file = open(output_filename, 'wb')

        # Construct the installation script and write it out.
        if not tarball:
            if output_filename == '-':
                base64_encoded_tarball = base64.b64encode(tar_stream.getvalue()).decode('utf-8')
                script_content = render_template_file('install-bundle-noninteractive.sh',
                    base64_encoded_tarball=base64_encoded_tarball)
                output_file.write(script_content.encode('utf-8'))
            else:
                output_file.write(render_template_file('install-bundle.sh').encode('utf-8'))
                output_file.write(tar_stream.getvalue())
        else:
            # Or just write out the tarball.
            output_file.write(tar_stream.getvalue())

        # Write out the success message.
        logger.info('Successfully created "%s".' % output_filename)
        return True
    except:  # noqa: E722
        raise
    finally:
        if root_directory:
            shutil.rmtree(root_directory)
        if output_file and output_filename:
            output_file.close()
            if not tarball and output_filename not in ['-', '/dev/null']:
                st = os.stat(output_filename)
                os.chmod(output_filename, st.st_mode | stat.S_IEXEC)


def create_unpackaged_bundle(executables, rename=[], chroot=None, add=[], no_symlink=[],
                             shell_launchers=False, detect=False):
    """Creates a temporary directory containing the unpackaged contents of the bundle."""
    bundle = Bundle(chroot=chroot, working_directory=True)
    try:
        # Sanitize the inputs.
        assert len(executables), 'No executables were specified.'
        assert len(executables) >= len(rename), \
            'More renamed options were included than executables.'
        # Pad the rename's with `True` so that `entry_point` can be specified.
        entry_points = rename + [True for i in range(len(executables) - len(rename))]

        # Populate the bundle with main executable files and their dependencies.
        for (executable, entry_point) in zip(executables, entry_points):
            file = bundle.add_file(executable, entry_point=entry_point)

            # We'll only auto-detect dependencies for these entry points as well.
            # If we did this later, it would practically bring in the whole system...
            if detect:
                dependency_paths = detect_dependencies(file.path)
                if not dependency_paths:
                    raise DependencyDetectionError(
                        ('Automatic dependency detection failed. Either "%s" ' % file.path) +
                        'is not tracked by your package manager, or your operating system '
                        'is not currently compatible with the `--detect` option. If not, please '
                        "create an issue at https://github.com/intoli/exodus and we'll try our "
                        ' to add support for it in the future.',
                    )

                for path in dependency_paths:
                    bundle.add_file(path)

        # Add "additional files" specified with the `--add` option.
        for filename in add:
            bundle.add_file(filename)

        # Mark the required files as `no_symlink=True`.
        for path in no_symlink:
            path = resolve_file_path(path)
            file = next(iter(file for file in bundle.files if file.path == path), None)
            if file:
                file.no_symlink = True

        bundle.create_bundle(shell_launchers=shell_launchers)

        return bundle.working_directory
    except:  # noqa: E722
        bundle.delete_working_directory()
        raise


def detect_elf_binary(filename):
    """Returns `True` if a file has an ELF header."""
    if not os.path.exists(filename):
        raise MissingFileError('The "%s" file was not found.' % filename)

    with open(filename, 'rb') as f:
        first_four_bytes = f.read(4)

    return first_four_bytes == b'\x7fELF'


def parse_dependencies_from_ldd_output(content):
    """Takes the output of `ldd` as a string or list of lines and parses the dependencies."""
    if type(content) == str:
        content = content.split('\n')

    dependencies = []
    for line in content:
        # This first one is a special case of invoking the linker as `ldd`.
        if re.search(r'^\s*(/.*?)\s*=>\s*ldd\s*\(', line):
            # We'll exclude this because it's the hardcoded INTERP path, and it would be
            # impossible to get the full path from this command output.
            continue
        match = re.search(r'=>\s*(/.*?)\s*\(', line)
        match = match or re.search(r'\s*(/.*?)\s*\(', line)
        if match:
            dependencies.append(match.group(1))

    return dependencies


def resolve_binary(binary):
    """Attempts to find the absolute path to the binary."""
    absolute_binary_path = os.path.normpath(os.path.abspath(binary))
    if not os.path.exists(absolute_binary_path):
        for path in os.getenv('PATH', '/bin/:/usr/bin/').split(os.pathsep):
            absolute_binary_path = os.path.normpath(os.path.abspath(os.path.join(path, binary)))
            if os.path.exists(absolute_binary_path):
                break
        else:
            raise MissingFileError('The "%s" binary could not be found in $PATH.' % binary)
    return absolute_binary_path


def resolve_file_path(path, search_environment_path=False):
    """Attempts to find a normalized path to a file.

    If the file is not found, or if it is a directory, appropriate exceptions will be thrown.

    Args:
        path (str): Either a relative or absolute path to a file, or the name of an
            executable if `search_environment_path` is `True`.
        search_environment_path (bool): Whether PATH should be used to resolve the file.
    """
    if search_environment_path:
        path = resolve_binary(path)
    if not os.path.exists(path):
        raise MissingFileError('The "%s" file was not found.' % path)
    if os.path.isdir(path):
        raise UnexpectedDirectoryError('"%s" is a directory, not a file.' % path)
    return os.path.normpath(os.path.abspath(path))


def run_ldd(ldd, binary):
    """Runs `ldd` and gets the combined stdout/stderr output as a list of lines."""
    if not detect_elf_binary(resolve_binary(binary)):
        raise InvalidElfBinaryError('The "%s" file is not a binary ELF file.' % binary)

    process = Popen([ldd, binary], stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()
    return stdout.decode('utf-8').split('\n') + stderr.decode('utf-8').split('\n')


class stored_property(object):
    """Simple decorator for a class property that will be cached indefinitely."""
    def __init__(self, function):
        self.__doc__ = getattr(function, '__doc__')
        self.function = function

    def __get__(self, instance, type):
        result = instance.__dict__[self.function.__name__] = self.function(instance)
        return result


class Elf(object):
    """Parses basic attributes from the ELF header of a file.

    Attributes:
        bits (int): The number of bits for an ELF binary, either 32 or 64.
        chroot (str): The root directory used when invoking the linker (or `None`).
        file_factory (function): A function used to create new `File` instances.
        linker_file (File): The linker/interpreter specified in the program header.
        path (str): The path to the file.
        type (str): The binary type, one of 'relocatable', 'executable', 'shared', or 'core'.
    """
    def __init__(self, path, chroot=None, file_factory=None):
        """Constructs the `Elf` instance.

        Args:
            path (str): The full path to the ELF binary.
            chroot (str, optional): If specified, all dependency and linker paths will be considered
                relative to this directory (mainly useful for testing).
            file_factory (function, optional): A function to use when creating new `File` instances.
        """
        if not os.path.exists(path):
            raise MissingFileError('The "%s" file was not found.' % path)
        self.path = path
        self.chroot = chroot
        self.file_factory = file_factory or File

        with open(path, 'rb') as f:
            # Make sure that this is actually an ELF binary.
            first_four_bytes = f.read(4)
            if first_four_bytes != b'\x7fELF':
                raise InvalidElfBinaryError('The "%s" file is not a binary ELF file.' % path)

            # Determine whether this is a 32-bit or 64-bit file.
            format_byte = f.read(1)
            self.bits = {b'\x01': 32, b'\x02': 64}.get(format_byte)
            if not self.bits:
                raise UnsupportedArchitectureError(
                    ('The "%s" file does not appear to be either 32 or 64 bits. ' % path) +
                    'Other architectures are not currently supported, but you can open an '
                    'issue at https://github.com/intoli/exodus stating your use-case and '
                    'support might get extended in the future.',
                )

            # Determine whether it's big or little endian and construct an integer parsing function.
            endian_byte = f.read(1)
            byteorder = {b'\x01': 'little', b'\x02': 'big'}[endian_byte]
            assert byteorder == 'little', 'Big endian is not supported right now.'
            if not byteorder:
                raise UnsupportedArchitectureError(
                    ('The "%s" file does not appear to be little endian, ' % path) +
                    'and big endian binaries are not currently supported. You can open an '
                    'issue at https://github.com/intoli/exodus stating your use-case and '
                    'support might get extended in the future.',
                )

            def hex(bytes):
                return bytes_to_int(bytes, byteorder=byteorder)

            # Determine the type of the binary.
            f.seek(hex(b'\x10'))
            e_type = hex(f.read(2))
            self.type = {1: 'relocatable', 2: 'executable', 3: 'shared', 4: 'core'}[e_type]

            # Find the program header offset.
            e_phoff_start = {32: hex(b'\x1c'), 64: hex(b'\x20')}[self.bits]
            e_phoff_length = {32: 4, 64: 8}[self.bits]
            f.seek(e_phoff_start)
            e_phoff = hex(f.read(e_phoff_length))

            # Determine the size of a program header entry.
            e_phentsize_start = {32: hex(b'\x2a'), 64: hex(b'\x36')}[self.bits]
            f.seek(e_phentsize_start)
            e_phentsize = hex(f.read(2))

            # Determine the number of program header entries.
            e_phnum_start = {32: hex(b'\x2c'), 64: hex(b'\x38')}[self.bits]
            f.seek(e_phnum_start)
            e_phnum = hex(f.read(2))

            # Loop through each program header.
            self.linker_file = None
            for header_index in range(e_phnum):
                header_start = e_phoff + header_index * e_phentsize
                f.seek(header_start)
                p_type = f.read(4)
                # A p_type of \x03 corresponds to a PT_INTERP header (e.g. the linker).
                if len(p_type) == 0:
                    break
                if not p_type == b'\x03\x00\x00\x00':
                    continue

                # Determine the offset for the segment.
                p_offset_start = header_start + {32: hex(b'\04'), 64: hex(b'\x08')}[self.bits]
                p_offset_length = {32: 4, 64: 8}[self.bits]
                f.seek(p_offset_start)
                p_offset = hex(f.read(p_offset_length))

                # Determine the size of the segment.
                p_filesz_start = header_start + {32: hex(b'\x10'), 64: hex(b'\x20')}[self.bits]
                p_filesz_length = {32: 4, 64: 8}[self.bits]
                f.seek(p_filesz_start)
                p_filesz = hex(f.read(p_filesz_length))

                # Read in the segment.
                f.seek(p_offset)
                segment = f.read(p_filesz)
                # It should be null-terminated (b'\x00' in Python 2, 0 in Python 3).
                assert segment[-1] in [b'\x00', 0], 'The string should be null terminated.'
                assert self.linker_file is None, 'More than one linker found.'
                linker_path = segment[:-1].decode('ascii')
                if chroot:
                    linker_path = os.path.join(chroot, os.path.relpath(linker_path, '/'))
                self.linker_file = self.file_factory(linker_path, chroot=self.chroot)

    def __eq__(self, other):
        return isinstance(other, Elf) and self.path == self.path

    def __hash__(self):
        """Defines a hash for the object so it can be used in sets."""
        return hash(self.path)

    def __repr__(self):
        return '<Elf(path="%s")>' % self.path

    def find_direct_dependencies(self, linker_file=None):
        """Runs the specified linker and returns a set of the dependencies as `File` instances."""
        linker_file = linker_file or self.linker_file
        if not linker_file:
            return set()
        linker_path = linker_file.path
        environment = {}
        environment.update(os.environ)
        environment['LD_TRACE_LOADED_OBJECTS'] = '1'
        extra_ldd_arguments = []
        if self.chroot:
            ld_library_path = '/lib64:/usr/lib64:/lib/:/usr/lib:/lib32/:/usr/lib32/:'
            ld_library_path += environment.get('LD_LIBRARY_PATH', '')
            directories = []
            for directory in ld_library_path.split(':'):
                if os.path.isabs(directory):
                    directory = os.path.join(self.chroot, os.path.relpath(directory, '/'))
                directories.append(directory)
            ld_library_path = ':'.join(directories)
            environment['LD_LIBRARY_PATH'] = ld_library_path
            # We only need to avoid including system dependencies if there's a chroot set.
            extra_ldd_arguments += ['--inhibit-cache', '--inhibit-rpath', '']

        process = Popen(['ldd'] + extra_ldd_arguments + [self.path],
                        executable=linker_path, stdout=PIPE, stderr=PIPE, env=environment)
        stdout, stderr = process.communicate()
        combined_output = stdout.decode('utf-8').split('\n') + stderr.decode('utf-8').split('\n')
        # Note that we're explicitly adding the linker because when we invoke it as `ldd` we can't
        # extract the real path from the trace output. Even if it were here twice, it would be
        # deduplicated though the use of a set.
        filenames = parse_dependencies_from_ldd_output(combined_output) + [linker_path]
        return set(self.file_factory(filename, chroot=self.chroot, library=True)
                   for filename in filenames)

    @stored_property
    def dependencies(self):
        """Run's the files' linker iteratively and returns a set of all library dependencies."""
        all_dependencies = set()
        unprocessed_dependencies = set(self.direct_dependencies)
        while len(unprocessed_dependencies):
            all_dependencies |= unprocessed_dependencies
            new_dependencies = set()
            for dependency in unprocessed_dependencies:
                if dependency.elf:
                    new_dependencies |= set(
                        dependency.elf.find_direct_dependencies(self.linker_file))
            unprocessed_dependencies = new_dependencies - all_dependencies
        return all_dependencies

    @stored_property
    def direct_dependencies(self):
        """Runs the file's linker and returns a set of the dependencies as `File` instances."""
        return self.find_direct_dependencies()


class File(object):
    """Represents a file on disk and provides access to relevant properties and actions.

    Note:
        The `File` class is tied to the bundling format. For example, the `destination` property
        will correspond to a path like 'data/{hash}' which is then used in bundling.

    Attributes:
        chroot (str): A location to treat as the root during dependency linking (or `None`).
        elf (Elf): A corresponding `Elf` object, or `None` if it is not an ELF formatted file.
        entry_point (str): The name of the bundle entry point for an executable binary (or `None`).
        file_factory (function): A function used to create new `File` instances.
        library (bool): Specifies that this file is explicitly a shared library.
        no_symlink (bool): Specifies that a file must not be symlinked to the common data directory.
        path (str): The absolute normalized path to the file on disk.
    """

    def __init__(self, path, entry_point=None, chroot=None, library=False, file_factory=None):
        """Constructor for the `File` class.

        Note:
            A `MissingFileError` will be thrown if a matching file cannot be found.

        Args:
            path (str): Can be either an absolute path, relative path, or a binary name in `PATH`.
            entry_point (string, optional): The name of the bundle entry point for an executable.
                If `True`, the executable's basename will be used.
            chroot (str, optional): If specified, all dependency and linker paths will be considered
                relative to this directory (mainly useful for testing).
            file_factory (function, optional): A function to use when creating new `File` instances.
        """
        # Find the full path to the file.
        self.path = resolve_file_path(path, search_environment_path=(entry_point is not None))

        # Set the entry point for the file.
        if entry_point is True:
            self.entry_point = os.path.basename(self.path).replace(os.sep, '')
        else:
            self.entry_point = entry_point or None

        # Parse an `Elf` object from the file.
        try:
            self.elf = Elf(path, chroot=chroot, file_factory=file_factory)
        except InvalidElfBinaryError:
            self.elf = None

        self.chroot = chroot
        self.file_factory = file_factory or File
        self.library = library
        self.no_symlink = self.entry_point and not self.requires_launcher

    def __eq__(self, other):
        return isinstance(other, File) and self.path == self.path and \
            self.entry_point == self.entry_point

    def __hash__(self):
        """Computes a hash for the instance unique up to the file path and entry point."""
        return hash((self.path, self.entry_point))

    def __repr__(self):
        return '<File(path="%s")>' % self.path

    def copy(self, working_directory):
        """Copies the file to a location based on its `destination` property.

        Args:
            working_directory (str): The root that the `destination` will be joined with.
        Returns:
            str: The normalized and absolute destination path.
        """
        full_destination = os.path.join(working_directory, self.destination)
        full_destination = os.path.normpath(os.path.abspath(full_destination))

        # The filenames are based on content hashes, so there's no need to copy it twice.
        if os.path.exists(full_destination):
            return full_destination

        parent_directory = os.path.dirname(full_destination)
        if not os.path.exists(parent_directory):
            os.makedirs(parent_directory)

        shutil.copy(self.path, full_destination)

        return full_destination

    def create_entry_point(self, working_directory, bundle_root):
        """Creates a symlink in `bin/` to the executable or its launcher.

        Note:
            The destination must already exist.
        Args:
            working_directory (str): The root that the `destination` will be joined with.
            bundle_root (str): The root that `source` will be joined with.
        """
        source_path = os.path.join(bundle_root, self.source)
        bin_directory = os.path.join(working_directory, 'bin')
        if not os.path.exists(bin_directory):
            os.makedirs(bin_directory)
        entry_point_path = os.path.join(bin_directory, self.entry_point)
        relative_destination_path = os.path.relpath(source_path, bin_directory)
        os.symlink(relative_destination_path, entry_point_path)

    def create_launcher(self, working_directory, bundle_root, linker_basename, symlink_basename,
                        shell_launcher=False):
        """Creates a launcher at `source` for `destination`.

        Note:
            If an `entry_point` has been specified, it will also be created.
        Args:
            working_directory (str): The root that the `destination` will be joined with.
            bundle_root (str): The root that `source` will be joined with.
            linker_basename (str): The basename of the linker to place in the same directory.
            symlink_basename (str): The basename of the symlink to the actual executable.
            shell_launcher (bool, optional): Forces the use of shell script launcher instead of
                attempting to compile first using musl or diet c.
        Returns:
            str: The normalized and absolute path to the launcher.
        """
        destination_path = os.path.join(working_directory, self.destination)
        source_path = os.path.join(bundle_root, self.source)

        # Create the symlink.
        source_parent = os.path.dirname(source_path)
        if not os.path.exists(source_parent):
            os.makedirs(source_parent)
        relative_destination_path = os.path.relpath(destination_path, source_parent)
        symlink_path = os.path.join(source_parent, symlink_basename)
        os.symlink(relative_destination_path, symlink_path)
        executable = os.path.join('.', symlink_basename)

        # Copy over the linker.
        linker_path = os.path.join(source_parent, linker_basename)
        if not os.path.exists(linker_path):
            shutil.copy(self.elf.linker_file.path, linker_path)
        else:
            assert filecmp.cmp(self.elf.linker_file.path, linker_path), \
                'The "%s" linker file already exists and has differing contents.' % linker_path
        linker = os.path.join('.', linker_basename)

        # Construct the library path
        original_file_parent = os.path.dirname(self.path)
        library_paths = os.environ.get('LD_LIBRARY_PATH', '').split(':')
        library_paths += ['/lib64', '/usr/lib64', '/lib', '/usr/lib', '/lib32', '/usr/lib32']
        for dependency in self.elf.dependencies:
            library_paths.append(os.path.dirname(dependency.path))
        relative_library_paths = []
        for directory in library_paths:
            if not len(directory):
                continue

            # Get the actual absolute path for the library directory.
            directory = os.path.normpath(os.path.abspath(directory))
            if self.chroot:
                directory = os.path.join(self.chroot, os.path.relpath(directory, '/'))

            # Convert it into a path relative to the launcher/source.
            relative_library_path = os.path.relpath(directory, original_file_parent)
            if relative_library_path not in relative_library_paths:
                relative_library_paths.append(relative_library_path)
        library_path = ':'.join(relative_library_paths)

        # Determine whether this is a "full" linker (*e.g.* GNU linker).
        with open(self.elf.linker_file.path, 'rb') as f:
            linker_content = f.read()
            full_linker = (linker_content.find(b'inhibit-rpath') > -1)

        # Try a c launcher first and fallback.
        try:
            if shell_launcher:
                raise CompilerNotFoundError()

            launcher_content = construct_binary_launcher(
                linker=linker, library_path=library_path, executable=executable,
                full_linker=full_linker)
            with open(source_path, 'wb') as f:
                f.write(launcher_content)
        except CompilerNotFoundError:
            if not shell_launcher:
                logger.warning((
                    'Installing either the musl or diet C libraries will result in more efficient '
                    'launchers (currently using bash fallbacks instead).'
                ))
            launcher_content = construct_bash_launcher(
                linker=linker, library_path=library_path, executable=executable,
                full_linker=full_linker)
            with open(source_path, 'w') as f:
                f.write(launcher_content)
        shutil.copymode(self.path, source_path)

        return os.path.normpath(os.path.abspath(source_path))

    def symlink(self, working_directory, bundle_root):
        """Creates a relative symlink from the `source` to the `destination`.

        Args:
            working_directory (str): The root that `destination` will be joined with.
            bundle_root (str): The root that `source` will be joined with.
        Returns:
            str: The normalized and absolute path to the symlink.
        """
        destination_path = os.path.join(working_directory, self.destination)
        source_path = os.path.join(bundle_root, self.source)

        source_parent = os.path.dirname(source_path)
        if not os.path.exists(source_parent):
            os.makedirs(source_parent)
        relative_destination_path = os.path.relpath(destination_path, source_parent)
        if os.path.exists(source_path):
            assert os.path.islink(source_path)
            assert os.path.realpath(source_path) == relative_destination_path
        else:
            os.symlink(relative_destination_path, source_path)

        return os.path.normpath(os.path.abspath(source_path))

    @stored_property
    def destination(self):
        """str: The relative path for the destination of the actual file contents."""
        return os.path.join('.', 'data', self.hash)

    @stored_property
    def executable(self):
        return os.access(self.path, os.X_OK)

    @stored_property
    def elf(self):
        """bool: Determines whether a file is a file is an ELF binary."""
        return detect_elf_binary(self.path)

    @stored_property
    def hash(self):
        """str: Computes a hash based on the file content, useful for file deduplication."""
        with open(self.path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    @stored_property
    def requires_launcher(self):
        """bool: Whether a launcher is necessary for this file."""
        # This is unfortunately a heuristic approach because many executables are compiled
        # as shared libraries, and many mostly-libraries are executable (*e.g.* glibc).

        # The easy ones.
        if self.library or not self.elf or not self.elf.linker_file or not self.executable:
            return False
        if self.elf.type == 'executable':
            return True
        if self.entry_point:
            return True

        # These will hopefully do more good than harm.
        bin_directories = ['/bin/', '/bin32/', '/bin64/']
        lib_directories = ['/lib/', '/lib32/', '/lib64/']
        in_bin_directory = any(directory in self.path for directory in bin_directories)
        in_lib_directory = any(directory in self.path for directory in lib_directories)
        if in_bin_directory and not in_lib_directory:
            return True
        if in_lib_directory and not in_bin_directory:
            return False

        # Most libraries will include `.so` in the filename.
        return re.search(r'\.so(?:\.|$)', self.path)

    @stored_property
    def source(self):
        """str: The relative path for the source of the actual file contents."""
        return os.path.relpath(self.path, '/')


class Bundle(object):
    """A collection of files to be included in a bundle and utilities for creating bundles.

    Attributes:
        chroot (str): The root directory used when invoking the linker (or `None` for `/`).
        files (:obj:`set` of :obj:`File`): The files to be included in the bundle.
        linker_files (:obj:`set` of :obj:`File`): A list of observed linker files.
        working_directory (str): The root directory where the bundles will be written and packaged.
    """
    def __init__(self, working_directory=None, chroot=None):
        """Constructor for the `Bundle` class.

        Args:
            working_directory (string, optional): The location where the bundle will be created on
                disk. A temporary directory will be constructed if specified as `True`. If left as
                `None`, some methods and properties will raise errors.
            chroot (str, optional): If specified, all absolute paths will be treated as being
                relative to this root (mainly useful for testing).
        """
        self.working_directory = working_directory
        if working_directory is True:
            self.working_directory = tempfile.mkdtemp(prefix='exodus-bundle-')
            # The permissions on the `mkdtemp()` directory will be extremely restricted by default,
            # so we'll modify them to to reflect the current umask.
            umask = os.umask(0)
            os.umask(umask)
            os.chmod(self.working_directory, 0o777 & ~umask)
        self.chroot = chroot
        self.files = set()
        self.linker_files = set()

    def add_file(self, path, entry_point=None):
        """Adds an additional file to the bundle.

        Note:
            All of the file's dependencies will additionally be pulled into the bundle if the file
            corresponds to a an ELF binary. This is true regardless of whether or not an entry point
            is specified for the binary.

        Args:
            path (str): Can be either an absolute path, relative path, or a binary name in `PATH`.
                Directories will be included recursively for non-entry point dependencies.
            entry_point (string, optional): The name of the bundle entry point for an executable.
                If `True`, the executable's basename will be used.
        Returns:
            The `File` that was added, or `None` if it was a directory that was added recursively.
        """
        try:
            file = self.file_factory(path, entry_point=entry_point, chroot=self.chroot)
        except UnexpectedDirectoryError:
            assert entry_point is None, "Directories can't have entry points."
            for root, directories, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    self.add_file(file_path)
            return

        self.files.add(file)
        if file.elf:
            if file.elf.linker_file:
                self.linker_files.add(file.elf.linker_file)
                self.files |= file.elf.dependencies
            else:
                # Manually set the linker if there isn't one in the program header,
                # and we've only seen one in all of the files that have been added.
                if len(self.linker_files) == 1:
                    [file.elf.linker_file] = self.linker_files
                    self.files |= file.elf.dependencies
                    # We definitely don't want a launcher for this file, so clear the linker.
                    file.elf.linker_file = None
                else:
                    logger.warning((
                        'An ELF binary without a suitable linker candidate was encountered. '
                        'Either no linker was found or there are multiple conflicting linkers.'
                    ))

        return file

    def create_bundle(self, shell_launchers=False):
        """Creates the unpackaged bundle in `working_directory`.

        Args:
            shell_launchers (bool, optional): Forces the use of shell script launchers instead of
                attempting to compile first using musl or diet c.
        """
        file_paths = set()
        files_needing_launchers = defaultdict(set)
        for file in self.files:
            # Store the file path to avoid collisions later.
            file_path = os.path.join(self.bundle_root, file.source)
            file_paths.add(file_path)

            # Create a symlink in `./bin/` if an entry point is specified.
            if file.entry_point:
                file.create_entry_point(self.working_directory, self.bundle_root)

            if file.no_symlink:
                # We'll need to copy the actual file into the bundle subdirectory in this
                # case so that it can locate resources using paths relative to the executable.
                parent_directory = os.path.dirname(file_path)
                if not os.path.exists(parent_directory):
                    os.makedirs(parent_directory)
                shutil.copy(file.path, file_path)
                continue

            # Copy over the actual file.
            file.copy(self.working_directory)

            if file.requires_launcher:
                # These are kind of complicated, we'll just store the requirements for now.
                directory_and_linker = (os.path.dirname(file_path), file.elf.linker_file)
                files_needing_launchers[directory_and_linker].add(file)
            else:
                file.symlink(working_directory=self.working_directory, bundle_root=self.bundle_root)

        # Now we need to write out one unique copy of each linker in each directory where it's
        # required. This is necessary so that `readlink("/proc/self/exe")` will return the correct
        # directory when programs use that to construct relative paths to resources.
        for ((directory, linker), executable_files) in files_needing_launchers.items():
            # First, we'll find a unique name for the linker in this directory and write it out.
            desired_linker_path = os.path.join(directory, 'linker-%s' % linker.hash)
            linker_path = desired_linker_path
            iteration = 2
            while linker_path in file_paths:
                linker_path = '%s-%d' % (desired_linker_path, iteration)
                iteration += 1
            file_paths.add(linker_path)
            linker_dirname, linker_basename = os.path.split(linker_path)
            if not os.path.exists(linker_dirname):
                os.makedirs(linker_dirname)
            shutil.copy(linker.path, linker_path)

            # Now we need to construct a launcher for each executable that depends on this linker.
            for file in executable_files:
                # We'll again attempt to find a unique available name, this time for the symlink
                # to the executable.
                file_basename = file.entry_point or os.path.basename(file.path)
                desired_symlink_path = os.path.join(directory, '%s-x' % file_basename)
                symlink_path = desired_symlink_path
                iteration = 2
                while symlink_path in file_paths:
                    symlink_path = '%s-%d' % (desired_symlink_path, iteration)
                    iteration += 1
                file_paths.add(symlink_path)
                symlink_basename = os.path.basename(symlink_path)
                file.create_launcher(self.working_directory, self.bundle_root,
                                     linker_basename, symlink_basename,
                                     shell_launcher=shell_launchers)

    def delete_working_directory(self):
        """Recursively deletes the working directory."""
        shutil.rmtree(self.working_directory)
        self.working_directory = None

    def file_factory(self, path, entry_point=None, chroot=None, library=False, file_factory=None):
        """Either creates a new `File`, or updates and returns one from `files`.

        This method can be used in place of `File.__init__()` when it is known that the `File`
        is going to end up being added to the `Bundle.files` set. The construction of a `File` is
        quite expensive due to the ELF parsing, so this allows avoiding the construction of `File`
        objects when an equivalent ones are already present in the set. Additionally, this allows
        for intelligent merging of properties between `File` objects. For example, a `File` with
        an entry point should always preserve that entry point, even if the file also gets added
        using `--add` or some other method without one.

        See the `File.__init__()` method for documentation of the arguments, they're identical.
        """
        # Attempt to find an existing file with the same normalized path in `self.files`.
        path = resolve_file_path(path, search_environment_path=entry_point is not None)
        file = next((file for file in self.files if file.path == path), None)
        if file is not None:
            assert entry_point == file.entry_point or not entry_point or not file.entry_point, \
                "The entry point property should always persist, but can't conflict."
            file.entry_point = file.entry_point or entry_point
            assert chroot == file.chroot, 'The chroot must match.'
            file.library = file.library or library
            assert not file.entry_point or not file.library, \
                "A file can't be both an entry point and a library."
            return file

        return File(path, entry_point, chroot, library, file_factory)

    @property
    def bundle_root(self):
        """str: The root directory of the bundle where the original file structure is mirrored."""
        path = os.path.join(self.working_directory, 'bundles', self.hash)
        return os.path.normpath(os.path.abspath(path))

    @property
    def hash(self):
        """str: Computes a hash based on the current contents of the bundle."""
        file_hashes = sorted(file.hash for file in self.files)
        combined_hashes = '\n'.join(file_hashes).encode('utf-8')
        return hashlib.sha256(combined_hashes).hexdigest()
