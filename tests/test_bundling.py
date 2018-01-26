import sys

from exodus.bundling import find_all_library_dependencies
from exodus.bundling import find_direct_library_dependencies
from exodus.bundling import run_ldd


def test_find_all_library_dependencies():
    all_dependencies = find_all_library_dependencies(sys.executable)
    direct_dependencies = find_direct_library_dependencies(sys.executable)
    assert set(direct_dependencies).issubset(all_dependencies), \
        'The direct dependencies should be a subset of all dependencies.'


def test_find_direct_library_dependencies():
    dependencies = find_direct_library_dependencies(sys.executable)
    assert all(dependency.startswith('/') for dependency in dependencies), \
        'Dependencies should be absolute paths.'
    assert any('libc.so' in line for line in run_ldd(sys.executable)), \
        '"libpc" was not found as a direct dependency of the python executable.'


def test_run_ldd():
    assert any('libc.so' in line for line in run_ldd(sys.executable)), \
        '"libc" was not found in the output of "ldd" for the python executable.'
