import os

from exodus.bundling import find_all_library_dependencies
from exodus.bundling import find_direct_library_dependencies
from exodus.bundling import run_ldd


parent_directory = os.path.dirname(os.path.realpath(__file__))
chroot = os.path.join(parent_directory, 'test-binaries', 'chroot')
ldd = os.path.join(chroot, 'bin', 'ldd')
executable = os.path.join(chroot, 'bin', 'fizz-buzz')


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


def test_run_ldd():
    assert any('libc.so' in line for line in run_ldd(ldd, executable)), \
        '"libc" was not found in the output of "ldd" for the executable.'
