import hashlib
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

from exodus.launchers import CompilerNotFoundError
from exodus.launchers import construct_bash_launcher
from exodus.launchers import construct_binary_launcher
from exodus.templating import render_template
from exodus.templating import render_template_file


logger = logging.getLogger(__name__)


def create_bundle(executables, output, tarball=False, rename=[], ldd='ldd'):
    """Handles the creation of the full bundle."""
    try:
        # Create a temporary unpackaged bundle for the executables.
        root_directory = create_unpackaged_bundle(executables, rename=rename, ldd=ldd)

        # Populate the filename template.
        output_filename = render_template(output,
            executables=('-'.join(os.path.basename(executable) for executable in executables)),
            extension=('tgz' if tarball else 'sh'),
        )

        if output_filename == '-':
            output_file = sys.stdout.buffer
        else:
            output_file = open(output_filename, 'wb')

        # Construct the header of the installation script and write it out.
        if not tarball:
            output_file.write(render_template_file('install-bundle.sh').encode('utf-8'))

        # Write out a gzipped tarball of the bundle
        with tarfile.open(fileobj=output_file, mode='w:gz') as tar:
            tar.add(root_directory, arcname='exodus')

        # Write out the success message.
        logger.info('Successfully created "%s".' % output_filename)
        return True
    finally:
        shutil.rmtree(root_directory)
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
        # Pad the rename's so that they have the same length for the `zip()` call.
        rename = rename + [None for i in range(len(executables) - len(rename))]
        for name, executable in zip(rename, executables):
            # Make the bundle sundirectories for this executable.
            binary_name = (name or os.path.basename(executable)).replace(os.sep, '')
            bundle_directory = os.path.join(bundles_directory, binary_name)
            bundle_bin_directory = os.path.join(bundle_directory, 'bin')
            os.makedirs(bundle_bin_directory)
            bundle_lib_directory = os.path.join(bundle_directory, 'lib')
            os.makedirs(bundle_lib_directory)

            # Copy over the library dependencies and link them.
            dependencies = find_all_library_dependencies(ldd, executable)
            for dependency in dependencies:
                # Create the `lib/{hash}` subdirectory.
                dependency_name = os.path.basename(dependency)
                dependency_hash = sha256_hash(dependency)
                dependency_directory = os.path.join(lib_directory, dependency_hash)

                # Create the actual library file if it doesn't exist.
                dependency_destination = os.path.join(dependency_directory, 'data')
                if not os.path.exists(dependency_directory):
                    os.makedirs(dependency_directory)
                    shutil.copy(dependency, dependency_destination)

                # Create a link to the actual file using the real library name.
                dependency_link = os.path.join(dependency_directory, dependency_name)
                if not os.path.exists(dependency_link):
                    os.symlink(os.path.join('.', 'data'), dependency_link)

                # Create a secondary link to *that* link from inside the bundle lib directory.
                bundle_dependency_link = os.path.join(bundle_lib_directory, dependency_name)
                relative_dependency_path = os.path.relpath(dependency_link, bundle_lib_directory)
                assert not os.path.exists(bundle_dependency_link), \
                    'The same library filename has been included more than once in a bundle.'
                os.symlink(relative_dependency_path, bundle_dependency_link)

            # Copy over the executable.
            bundle_executable_path = os.path.join(bundle_bin_directory, binary_name)
            shutil.copy(executable, bundle_executable_path)

            # Construct the launcher.
            linker_candidates = list(filter(lambda candidate: candidate.startswith('ld-'), (
                os.path.basename(dependency) for dependency in dependencies
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
    finally:
        return root_directory


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
    matches = filter(None, (re.search('=>\s*([^(]*?)\s*\(', line) for line in run_ldd(ldd, binary)))
    return [match.group(1) for match in matches]


def run_ldd(ldd, binary):
    """Runs `ldd` and gets the combined stdout/stderr output as a list of lines."""
    if not os.path.exists(binary):
        raise FileNotFoundError('"%s" is not a file.')
    process = Popen([ldd, binary], stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()
    return stdout.decode('utf-8').split('\n') + stderr.decode('utf-8').split('\n')


def sha256_hash(filename):
    with open(filename, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()
