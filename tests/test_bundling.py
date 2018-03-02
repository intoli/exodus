import os
import shutil
from subprocess import PIPE
from subprocess import Popen

import pytest

from exodus_bundler.bundling import Bundle
from exodus_bundler.bundling import Elf
from exodus_bundler.bundling import File
from exodus_bundler.bundling import bytes_to_int
from exodus_bundler.bundling import create_unpackaged_bundle
from exodus_bundler.bundling import detect_elf_binary
from exodus_bundler.bundling import parse_dependencies_from_ldd_output
from exodus_bundler.bundling import resolve_binary
from exodus_bundler.bundling import run_ldd
from exodus_bundler.bundling import stored_property


parent_directory = os.path.dirname(os.path.realpath(__file__))
ldd_output_directory = os.path.join(parent_directory, 'data', 'ldd-output')
chroot = os.path.join(parent_directory, 'data', 'binaries', 'chroot')
ldd = os.path.join(chroot, 'bin', 'ldd')
fizz_buzz_glibc_32 = os.path.join(chroot, 'bin', 'fizz-buzz-glibc-32')
fizz_buzz_glibc_32_exe = os.path.join(chroot, 'bin', 'fizz-buzz-glibc-32-exe')
fizz_buzz_glibc_64 = os.path.join(chroot, 'bin', 'fizz-buzz-glibc-64')
fizz_buzz_musl_64 = os.path.join(chroot, 'bin', 'fizz-buzz-musl-64')


@pytest.mark.parametrize('path,expected_file_count', [
    (fizz_buzz_glibc_32, 3),
    (fizz_buzz_glibc_64, 3),
    (fizz_buzz_musl_64, 2),
    (ldd, 1),
])
def test_bundle_add_file(path, expected_file_count):
    bundle = Bundle(chroot=chroot)
    assert len(bundle.files) == 0, 'The initial bundle should contain no files.'
    bundle.add_file(path)
    assert len(bundle.files) == expected_file_count, \
        'The bundle should include %d files.' % expected_file_count


def test_bundle_delete_working_directory():
    bundle = Bundle()
    assert bundle.working_directory is None, \
        'A directory should only be created if passed `working_directory=True`.'
    bundle = Bundle(working_directory=True)
    working_directory = bundle.working_directory
    assert os.path.exists(working_directory), \
        'A working directory should have been created.'
    bundle.delete_working_directory()
    assert not os.path.exists(working_directory), \
        'The working directory should have been deleted.'
    assert bundle.working_directory is None, \
        'The working directory should have been cleared after deletion.'


def test_bundle_hash():
    bundle = Bundle(chroot=chroot)
    hashes = [bundle.hash]
    for filename in [fizz_buzz_glibc_32, fizz_buzz_glibc_64, fizz_buzz_musl_64]:
        bundle.add_file(filename)
        hashes.append(bundle.hash)
    assert len(hashes) == len(set(hashes)), 'All of the hashes should be unique.'
    assert all(len(hash) == 64 for hash in hashes), 'All of the hashes should have length 64.'


def test_bundle_root():
    try:
        bundle = Bundle(working_directory=True)
        assert bundle.hash in bundle.bundle_root, 'Bundle path should include the hash.'
        assert bundle.bundle_root.startswith(bundle.working_directory), \
            'The bundle root should be a subdirectory of the working directory.'
    except: # noqa: E722
        raise
    finally:
        bundle.delete_working_directory()


@pytest.mark.parametrize('int,bytes,byteorder', [
    (1234567890, b'\xd2\x02\x96I\x00\x00\x00\x00', 'little'),
    (1234567890, b'\x00\x00\x00\x00I\x96\x02\xd2', 'big'),
    (9876543210, b'\xea\x16\xb0L\x02\x00\x00\x00', 'little'),
    (9876543210, b'\x00\x00\x00\x02L\xb0\x16\xea', 'big'),
])
def test_bytes_to_int(int, bytes, byteorder):
    assert bytes_to_int(bytes, byteorder=byteorder) == int, 'Byte conversion should work.'


def test_create_unpackaged_bundle():
    """This tests that the packaged executable runs as expected. At the very least, this
    tests that the symbolic links and launcher are functioning correctly. Unfortunately,
    it doesn't really test the linker overrides unless the required libraries are not
    present on the current system. FWIW, the CircleCI docker image being used is
    incompatible, so the continuous integration tests are more meaningful."""
    root_directory = create_unpackaged_bundle(
        rename=[], executables=[fizz_buzz_glibc_32], chroot=chroot)
    try:
        binary_path = os.path.join(root_directory, 'bin', os.path.basename(fizz_buzz_glibc_32))

        process = Popen([binary_path], stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        assert 'FIZZBUZZ' in stdout.decode('utf-8')
        assert len(stderr.decode('utf-8')) == 0
    finally:
        assert root_directory.startswith('/tmp/')
        shutil.rmtree(root_directory)


def test_detect_elf_binary():
    assert detect_elf_binary(fizz_buzz_glibc_32), 'The `fizz-buzz` file should be an ELF binary.'
    assert not detect_elf_binary(ldd), 'The `ldd` file should be a shell script.'


@pytest.mark.parametrize('fizz_buzz,bits', [
    (fizz_buzz_glibc_32, 32),
    (fizz_buzz_glibc_64, 64),
    (fizz_buzz_musl_64, 64),
])
def test_elf_bits(fizz_buzz, bits):
    fizz_buzz_elf = Elf(fizz_buzz)
    # Can be checked by running `file fizz-buzz`.
    assert fizz_buzz_elf.bits == bits, \
        'The fizz buzz executable should be %d-bit.' % bits


@pytest.mark.parametrize('fizz_buzz', [
    (fizz_buzz_glibc_32),
    (fizz_buzz_glibc_64),
])
def test_elf_dependencies(fizz_buzz):
    fizz_buzz_elf = Elf(fizz_buzz, chroot=chroot)
    direct_dependencies = fizz_buzz_elf.direct_dependencies
    all_dependencies = fizz_buzz_elf.dependencies
    assert set(direct_dependencies).issubset(all_dependencies), \
        'The direct dependencies should be a subset of all dependencies.'


@pytest.mark.parametrize('fizz_buzz', [
    (fizz_buzz_glibc_32),
    (fizz_buzz_glibc_64),
    (fizz_buzz_musl_64),
])
def test_elf_direct_dependencies(fizz_buzz):
    fizz_buzz_elf = Elf(fizz_buzz, chroot=chroot)
    dependencies = fizz_buzz_elf.direct_dependencies
    assert all(file.path.startswith(chroot) for file in dependencies), \
        'All dependencies should be located within the chroot.'
    assert len(dependencies), 'There should be at least one dependency.'

    # These don't apply to the musl binary.
    if 'glib' in fizz_buzz:
        assert len(dependencies) == 2, 'The linker and libc should be the only dependencies.'
        assert any('libc.so' in file.path for file in dependencies), \
            '"libc" was not found as a direct dependency of the executable.'


@pytest.mark.parametrize('fizz_buzz,expected_linker', [
    (fizz_buzz_glibc_32, '/lib/ld-linux.so.2'),
    (fizz_buzz_glibc_64, '/lib64/ld-linux-x86-64.so.2'),
    (fizz_buzz_musl_64, '/lib/ld-musl-x86_64.so.1'),
])
def test_elf_linker(fizz_buzz, expected_linker):
    # Found by running `readelf -l fizz-buzz`.
    fizz_buzz_elf = Elf(fizz_buzz)
    assert fizz_buzz_elf.linker == expected_linker, \
        'The correct linker should be extracted from the ELF program header.'


@pytest.mark.parametrize('fizz_buzz, expected_type', [
    (fizz_buzz_glibc_32, 'shared'),
    (fizz_buzz_glibc_32_exe, 'executable'),
    (fizz_buzz_glibc_64, 'shared'),
])
def test_elf_type(fizz_buzz, expected_type):
    elf = Elf(fizz_buzz)
    assert elf.type == expected_type, 'Fizz buzz should match the expected ELF binary type.'


def test_file_destination():
    arch_file = File(os.path.join(ldd_output_directory, 'htop-arch.txt'))
    arch_directory = os.path.dirname(arch_file.destination)
    fizz_buzz_file = File(fizz_buzz_glibc_32)
    fizz_buzz_directory = os.path.dirname(fizz_buzz_file.destination)
    assert arch_directory != fizz_buzz_directory, \
        'Executable and non-executable files should not be written to the same directory.'


def test_file_executable():
    fizz_buzz_file = File(fizz_buzz_glibc_32)
    arch_file = File(os.path.join(ldd_output_directory, 'htop-arch.txt'))
    assert fizz_buzz_file.executable, 'The fizz buzz executable should be executable.'
    assert not arch_file.executable, 'The arch text file should not be executable.'


def test_file_elf():
    fizz_buzz_file = File(fizz_buzz_glibc_32)
    arch_file = File(os.path.join(ldd_output_directory, 'htop-arch.txt'))
    assert fizz_buzz_file.elf, 'The fizz buzz executable should be an ELF binary.'
    assert not arch_file.elf, 'The arch text file should not be an ELF binary.'


def test_file_hash():
    amazon_file = File(os.path.join(ldd_output_directory, 'htop-amazon-linux.txt'))
    arch_file = File(os.path.join(ldd_output_directory, 'htop-arch.txt'))
    assert amazon_file.hash != arch_file.hash, 'The hashes should differ.'
    assert len(amazon_file.hash) == len(arch_file.hash) == 64, \
        'The hashes should have a consistent length of 64 characters.'

    # Found by executing `sha256sum fizz-buzz`.
    expected_hash = 'd54ab4714215d7822bf490df5cdf49bc3f32b4c85a439b109fc7581355f9d9c5'
    assert File(fizz_buzz_glibc_32).hash == expected_hash, 'Hashes should match.'


@pytest.mark.parametrize('fizz_buzz', [
    (fizz_buzz_glibc_32),
    (fizz_buzz_glibc_64),
    (fizz_buzz_musl_64),
])
def test_file_requires_launcher(fizz_buzz):
    file = File(fizz_buzz)
    assert file.requires_launcher, 'Fizz buzz should require a launcher.'
    assert all(not dependency.requires_launcher for dependency in file.elf.dependencies), \
        'All of the dependencies should not require launchers.'


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

    assert set(dependencies) == set(expected_dependencies), \
        'The dependencies were not parsed correctly from ldd output for "%s"' % filename_prefix


def test_resolve_binary():
    binary_directory = os.path.dirname(fizz_buzz_glibc_32)
    binary = os.path.basename(fizz_buzz_glibc_32)
    old_path = os.getenv('PATH', '')
    try:
        os.environ['PATH'] = '%s%s%s' % (binary_directory, os.pathsep, old_path)
        resolved_binary = resolve_binary(binary)
        assert resolved_binary == os.path.normpath(fizz_buzz_glibc_32), \
            'The full binary path was not resolved correctly.'
    finally:
        os.environ['PATH'] = old_path


def test_run_ldd():
    assert any('libc.so' in line for line in run_ldd(ldd, fizz_buzz_glibc_32)), \
        '"libc" was not found in the output of "ldd" for the executable.'


def test_stored_property():
    class Incrementer(object):
        def __init__(self):
            self.i = 0

        @stored_property
        def next(self):
            self.i += 1
            return self.i

    incrementer = Incrementer()
    for i in range(10):
        assert incrementer.next == 1, '`Incrementer.next` should not change.'
