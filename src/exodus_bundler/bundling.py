import base64
import hashlib
import io
import logging
import os
import re
import shutil
import stat
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

            # Create `File` instances for all of the library dependencies.
            dependency_files = set(
                File(dependency)
                for dependency in find_all_library_dependencies(ldd, executable_file.path)
            )

            # Copy over the library dependencies and link them.
            for dependency_file in dependency_files:
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
            linker_candidates = list(filter(lambda candidate: candidate.startswith('ld-'), (
                os.path.basename(dependency_file.path) for dependency_file in dependency_files
            )))
            assert len(linker_candidates) > 0, 'No linker candidates found.'
            assert len(linker_candidates) < 2, 'Multiple linker candidates found.'
            [linker] = linker_candidates
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


class File(object):
    """Represents a file on disk and provides access to relevant properties and actions.

    Attributes:
        entry_point (str): The name of the bundle entry point for an executable binary (or `None`).
        path (str): The absolute normalized path to the file on disk.
    """

    def __init__(self, path, entry_point=None):
        """Constructor for the `File` class.

        Note:
            A `MissingFileError` will be thrown if a matching file cannot be found.

        Args:
            path (str): Can be either an absolute path, relative path, or a binary name in `PATH`.
            entry_point (string): The name of the bundle entry point for an executable. If `True`,
                the executable's basename will be used.
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

    def __hash__(self):
        """Computes a hash for the instance unique up to the file path and entry point."""
        return hash((self.path, self.entry_point))
