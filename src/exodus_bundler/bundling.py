import base64
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
from subprocess import PIPE
from subprocess import Popen

from exodus_bundler.errors import InvalidElfBinaryError
from exodus_bundler.errors import LibraryConflictError
from exodus_bundler.errors import MissingFileError
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


def create_bundle(executables, output, tarball=False, rename=[], ldd='ldd'):
    """Handles the creation of the full bundle."""
    # Initialize these ahead of time so they're always available for error handling.
    output_filename, output_file, root_directory = None, None, None
    try:

        # Create a temporary unpackaged bundle for the executables.
        root_directory = create_unpackaged_bundle(executables, rename=rename, ldd=ldd)

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
            if output_filename == '-':
                output_file.close()
            else:
                st = os.stat(output_filename)
                os.chmod(output_filename, st.st_mode | stat.S_IEXEC)


def create_unpackaged_bundle(executables, rename=[], ldd='ldd'):
    """Creates a temporary directory containing the unpackaged contents of the bundle."""
    root_directory = tempfile.mkdtemp(prefix='exodus-bundle-')
    try:
        # Make the top-level bundle directories.
        bin_directory = os.path.join(root_directory, 'bin')
        os.makedirs(bin_directory)
        lib_directory = os.path.join(root_directory, 'lib')
        os.makedirs(lib_directory)
        bundles_directory = os.path.join(root_directory, 'bundles')

        # Loop through and package each executable.
        assert len(executables), 'No executables were specified.'
        assert len(executables) >= len(rename), \
            'More renamed options were included than executables.'
        # Pad the rename's with `True` so that `entry_point` can be specified.
        entry_points = rename + [True for i in range(len(executables) - len(rename))]

        # Create `File` instances of the executables.
        executable_files = set(
            File(executable, entry_point)
            for (executable, entry_point) in zip(executables, entry_points)
        )

        for executable_file in executable_files:
            # Make the bundle subdirectories for this executable.
            binary_name = executable_file.entry_point
            bundle_directory = os.path.join(bundles_directory, executable_file.hash)
            bundle_bin_directory = os.path.join(bundle_directory, 'bin')
            os.makedirs(bundle_bin_directory)
            bundle_lib_directory = os.path.join(bundle_directory, 'lib')
            os.makedirs(bundle_lib_directory)

            # Copy over the library dependencies and link them.
            for dependency_file in executable_file.elf.dependencies:
                # Create the `lib/{hash}` library file.
                dependency_name = os.path.basename(dependency_file.path)
                dependency_path = os.path.join(lib_directory, dependency_file.hash)
                if not os.path.exists(dependency_path):
                    shutil.copy(dependency_file.path, dependency_path)

                # Create a link to the actual library from inside the bundle lib directory.
                bundle_dependency_link = os.path.join(bundle_lib_directory, dependency_name)
                relative_dependency_path = os.path.relpath(dependency_path, bundle_lib_directory)
                if not os.path.exists(bundle_dependency_link):
                    os.symlink(relative_dependency_path, bundle_dependency_link)
                else:
                    link_destination = os.readlink(bundle_dependency_link)
                    link_destination = os.path.join(bundle_lib_directory, link_destination)
                    # This is only a problem if the duplicate libraries have different content.
                    if os.path.normpath(link_destination) != os.path.normpath(dependency_path):
                        raise LibraryConflictError(
                            'A library called "%s" was linked more than once.' % dependency_name)

            # Copy over the executable.
            bundle_executable_path = os.path.join(bundle_bin_directory, binary_name)
            shutil.copy(executable_file.path, bundle_executable_path)

            # Construct the launcher.
            linker = os.path.basename(executable_file.elf.linker)
            # Try a c launcher first and fallback.
            try:
                launcher_path = '%s-launcher' % bundle_executable_path
                launcher_content = construct_binary_launcher(linker=linker, binary=binary_name)
                with open(launcher_path, 'wb') as f:
                    f.write(launcher_content)
            except CompilerNotFoundError:
                logger.warn((
                    'Installing either the musl or diet C libraries will result in more efficient '
                    'launchers (currently using bash fallbacks instead).'
                ))
                launcher_path = '%s-launcher.sh' % bundle_executable_path
                launcher_content = construct_bash_launcher(linker=linker, binary=binary_name)
                with open(launcher_path, 'w') as f:
                    f.write(launcher_content)
            shutil.copymode(bundle_executable_path, launcher_path)
            executable_link = os.path.join(bin_directory, binary_name)
            relative_launcher_path = os.path.relpath(launcher_path, bin_directory)
            os.symlink(relative_launcher_path, executable_link)

        return root_directory
    except:  # noqa: E722
        shutil.rmtree(root_directory)
        raise


def detect_elf_binary(filename):
    """Returns `True` if a file has an ELF header."""
    if not os.path.exists(filename):
        raise MissingFileError('The "%s" file was not found.' % filename)

    with open(filename, 'rb') as f:
        first_four_bytes = f.read(4)

    return first_four_bytes == b'\x7fELF'


def find_all_library_dependencies(ldd, binary):
    """Finds all libraries that a binary directly or indirectly links to."""
    all_dependencies = set()
    unprocessed_dependencies = set(find_direct_library_dependencies(ldd, binary))
    while len(unprocessed_dependencies):
        all_dependencies |= unprocessed_dependencies
        new_dependencies = set()
        for dependency in unprocessed_dependencies:
            new_dependencies |= set(find_direct_library_dependencies(ldd, dependency))
        unprocessed_dependencies = new_dependencies - all_dependencies
    return list(all_dependencies)


def find_direct_library_dependencies(ldd, binary):
    """Finds the libraries that a binary directly links to."""
    return parse_dependencies_from_ldd_output(run_ldd(ldd, binary))


def parse_dependencies_from_ldd_output(content):
    """Takes the output of `ldd` as a string or list of lines and parses the dependencies."""
    if type(content) == str:
        content = content.split('\n')

    dependencies = []
    for line in content:
        # This first one is a special case of invoke the linker as `ldd`.
        if re.search('^\s*(/.*?)\s*=>\s*ldd\s*\(', line):
            # We'll exclude this because it's the hardcoded INTERP path, and it would be
            # impossible to get the full path from this command output.
            continue
        match = re.search('=>\s*(/.*?)\s*\(', line)
        match = match or re.search('\s*(/.*?)\s*\(', line)
        if match:
            dependencies.append(match.group(1))

    return dependencies


def resolve_binary(binary):
    """Attempts to find the absolute path to the binary."""
    absolute_binary_path = os.path.normpath(os.path.abspath(binary))
    if not os.path.exists(absolute_binary_path):
        for path in os.getenv('PATH', '').split(os.pathsep):
            absolute_binary_path = os.path.normpath(os.path.abspath(os.path.join(path, binary)))
            if os.path.exists(absolute_binary_path):
                break
        else:
            raise MissingFileError('The "%s" binary could not be found in $PATH.' % binary)
    return absolute_binary_path


def run_ldd(ldd, binary):
    """Runs `ldd` and gets the combined stdout/stderr output as a list of lines."""
    if not detect_elf_binary(resolve_binary(binary)):
        raise InvalidElfBinaryError('The "%s" file is not a binary ELF file.' % binary)

    process = Popen([ldd, binary], stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()
    return stdout.decode('utf-8').split('\n') + stderr.decode('utf-8').split('\n')


class stored_property(object):
    """Simple decoratator for a class property that will be cached indefinitely."""
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
        linker (str): The linker/interpreter specified in the program header.
        path (str): The path to the file.
    """
    def __init__(self, path, chroot=None):
        """Constructs the `Elf` instance.

        Args:
            path (str): The full path to the ELF binary.
            chroot (str, optional): If specified, all absolute paths will be treated as being
                relative to this root (mainly useful for testing).
        """
        if not os.path.exists(path):
            raise MissingFileError('The "%s" file was not found.' % path)
        self.path = path
        self.chroot = chroot

        with open(path, 'rb') as f:
            # Make sure that this is actually an ELF binary.
            first_four_bytes = f.read(4)
            if first_four_bytes != b'\x7fELF':
                raise InvalidElfBinaryError('The "%s" file is not a binary ELF file.' % path)

            # Determine whether this is a 32-bit or 64-bit file.
            format_byte = f.read(1)
            self.bits = {b'\x01': 32, b'\x02': 64}[format_byte]

            # Determine whether it's big or little endian and construct an integer parsing function.
            endian_byte = f.read(1)
            byteorder = {b'\x01': 'little', b'\x02': 'big'}[endian_byte]
            assert byteorder == 'little', 'Big endian is not supported right now.'

            def hex(bytes):
                return bytes_to_int(bytes, byteorder=byteorder)

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
            self.linker = None
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
                assert self.linker is None, 'More than one linker found.'
                self.linker = segment[:-1].decode('ascii')
                if chroot:
                    self.linker = os.path.join(chroot, os.path.relpath(self.linker, '/'))

    def __eq__(self, other):
        return isinstance(other, Elf) and self.path == self.path

    def __hash__(self):
        """Defines a hash for the object so it can be used in sets."""
        return hash(self.path)

    def __repr__(self):
        return '<Elf(path="%s")>' % self.path

    def find_direct_dependencies(self, linker=None):
        """Runs the specified linker and returns a set of the dependencies as `File` instances."""
        linker = linker or self.linker
        environment = {}
        environment.update(os.environ)
        environment['LD_TRACE_LOADED_OBJECTS'] = '1'
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

        process = Popen(['ldd', '--inhibit-cache', '--inhibit-rpath', '', self.path],
                        executable=linker, stdout=PIPE, stderr=PIPE, env=environment)
        stdout, stderr = process.communicate()
        combined_output = stdout.decode('utf-8').split('\n') + stderr.decode('utf-8').split('\n')
        # Note that we're explicitly adding the linker because when we invoke it as `ldd` we can't
        # extract the real path from the trace output. Even if it were here twice, it would be
        # deduplicated though the use of a set.
        filenames = parse_dependencies_from_ldd_output(combined_output) + [linker]
        return set(File(filename, chroot=self.chroot) for filename in filenames)

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
                    new_dependencies |= set(dependency.elf.find_direct_dependencies(self.linker))
            unprocessed_dependencies = new_dependencies - all_dependencies
        return all_dependencies

    @stored_property
    def direct_dependencies(self):
        """Runs the file's linker and returns a set of the dependencies as `File` instances."""
        return self.find_direct_dependencies()


class File(object):
    """Represents a file on disk and provides access to relevant properties and actions.

    Attributes:
        elf (Elf): A corresponding `Elf` object, or `None` if it is not an ELF formatted file.
        entry_point (str): The name of the bundle entry point for an executable binary (or `None`).
        path (str): The absolute normalized path to the file on disk.
    """

    def __init__(self, path, entry_point=None, chroot=None):
        """Constructor for the `File` class.

        Note:
            A `MissingFileError` will be thrown if a matching file cannot be found.

        Args:
            path (str): Can be either an absolute path, relative path, or a binary name in `PATH`.
            entry_point (string): The name of the bundle entry point for an executable. If `True`,
                the executable's basename will be used.
            chroot (str, optional): If specified, all absolute paths will be treated as being
                relative to this root (mainly useful for testing).
        """
        # Find the full path to the file.
        if entry_point:
            path = resolve_binary(path)
        if not os.path.exists(path):
            raise MissingFileError('The "%s" file was not found.' % path)
        self.path = os.path.normpath(os.path.abspath(path))

        # Set the entry point for the file.
        if entry_point is True:
            self.entry_point = os.path.basename(self.path).replace(os.sep, '')
        else:
            self.entry_point = entry_point or None

        # Parse an `Elf` object from the file.
        try:
            self.elf = Elf(path, chroot=chroot)
        except InvalidElfBinaryError:
            self.elf = None
        self.chroot = chroot

    def __eq__(self, other):
        return isinstance(other, File) and self.path == self.path and \
            self.entry_point == self.entry_point

    def __repr__(self):
        return '<File(path="%s")>' % self.path

    @stored_property
    def hash(self):
        """str: Computes a hash based on the file content, useful for file deduplication."""
        with open(self.path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def __hash__(self):
        """Computes a hash for the instance unique up to the file path and entry point."""
        return hash((self.path, self.entry_point))
