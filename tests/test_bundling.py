import os
import shutil
from subprocess import PIPE
from subprocess import Popen

import pytest

from exodus_bundler.bundling import create_unpackaged_bundle
from exodus_bundler.bundling import detect_elf_binary
from exodus_bundler.bundling import find_all_library_dependencies
from exodus_bundler.bundling import find_direct_library_dependencies
from exodus_bundler.bundling import parse_dependencies_from_ldd_output
from exodus_bundler.bundling import resolve_binary
from exodus_bundler.bundling import run_ldd
from exodus_bundler.bundling import sha256_hash


parent_directory = os.path.dirname(os.path.realpath(__file__))
ldd_output_directory = os.path.join(parent_directory, 'data', 'ldd-output')
chroot = os.path.join(parent_directory, 'data', 'binaries', 'chroot')
ldd = os.path.join(chroot, 'bin', 'ldd')
executable = os.path.join(chroot, 'bin', 'fizz-buzz')


def test_create_unpackaged_bundle():
    """This tests that the packaged executable runs as expected. At the very least, this
    tests that the symbolic links and launcher are functioning correctly. Unfortunately,
    it doesn't really test the linker overrides unless the required libraries are not
    present on the current system. FWIW, the CircleCI docker image being used is
    incompatible, so the continuous integration tests are more meaningful."""
    root_directory = create_unpackaged_bundle(rename=[], executables=[executable], ldd=ldd)
    try:
        binary_path = os.path.join(root_directory, 'bin', os.path.basename(executable))

        process = Popen([binary_path], stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        assert 'FIZZBUZZ' in stdout.decode('utf-8')
        assert len(stderr.decode('utf-8')) == 0
    finally:
        assert root_directory.startswith('/tmp/')
        shutil.rmtree(root_directory)


def test_detect_elf_binary():
    assert detect_elf_binary(executable), 'The `fizz-buzz` file should be an ELF binary.'
    assert not detect_elf_binary(ldd), 'The `ldd` file should be a shell script.'


def test_find_all_library_dependencies():
    all_dependencies = find_all_library_dependencies(ldd, executable)
    direct_dependencies = find_direct_library_dependencies(ldd, executable)
    assert set(direct_dependencies).issubset(all_dependencies), \
        'The direct dependencies should be a subset of all dependencies.'


def test_find_direct_library_dependencies():
    dependencies = find_direct_library_dependencies(ldd, executable)
    assert all(dependency.startswith('/') for dependency in dependencies), \
        'Dependencies should be absolute paths.'
    assert any('libc.so' in line for line in run_ldd(ldd, executable)), \
        '"libc" was not found as a direct dependency of the executable.'


@pytest.mark.parametrize('filename_prefix', [
    'htop-amazon-linux',
    'htop-arch',
    'htop-ubuntu-14.04',
])
def test_parse_dependencies_from_ldd_output(filename_prefix):
    ldd_output_filename = filename_prefix + '.txt'
    with open(os.path.join(ldd_output_directory, ldd_output_filename)) as f:
        ldd_output = f.read()
    dependencies = parse_dependencies_from_ldd_output(ldd_output)

    ldd_results_filename = filename_prefix + '-dependencies.txt'
    with open(os.path.join(ldd_output_directory, ldd_results_filename)) as f:
        expected_dependencies = [line for line in f.read().split('\n') if len(line)]
    print(dependencies)
    print(expected_dependencies)

    assert set(dependencies) == set(expected_dependencies), \
        'The dependencies were not parsed correctly from ldd output for "%s"' % filename_prefix


def test_resolve_binary():
    binary_directory = os.path.dirname(executable)
    binary = os.path.basename(executable)
    old_path = os.getenv('PATH', '')
    try:
        os.environ['PATH'] = '%s%s%s' % (binary_directory, os.pathsep, old_path)
        resolved_binary = resolve_binary(binary)
        assert resolved_binary == os.path.normpath(executable), \
            'The full binary path was not resolved correctly.'
    finally:
        os.environ['PATH'] = old_path


def test_run_ldd():
    assert any('libc.so' in line for line in run_ldd(ldd, executable)), \
        '"libc" was not found in the output of "ldd" for the executable.'


def test_sha256_hash():
    # Found by executing `sha256sum fizz-buzz`.
    expected_hash = 'd54ab4714215d7822bf490df5cdf49bc3f32b4c85a439b109fc7581355f9d9c5'
    assert sha256_hash(executable) == expected_hash
