import sys

from exodus.bundling import run_ldd


def test_run_ldd():
    assert any('libpython' in line for line in run_ldd(sys.executable)), \
        '"libpython" was not found in the output of "ldd" for the python executable.'
