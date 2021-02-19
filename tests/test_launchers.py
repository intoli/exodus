# -*- coding: utf-8 -*-
import os
import shutil
import stat
import tempfile
from subprocess import PIPE
from subprocess import Popen

import pytest

from exodus_bundler import launchers
from exodus_bundler.bundling import create_unpackaged_bundle
from exodus_bundler.launchers import CompilerNotFoundError
from exodus_bundler.launchers import compile_diet
from exodus_bundler.launchers import compile_musl
from exodus_bundler.launchers import construct_bash_launcher
from exodus_bundler.launchers import find_executable


parent_directory = os.path.dirname(os.path.realpath(__file__))
chroot = os.path.join(parent_directory, 'data', 'binaries', 'chroot')
echo_args_glibc_32 = os.path.join(chroot, 'bin', 'echo-args-glibc-32')
fizz_buzz_source_file = os.path.join(parent_directory, 'data', 'binaries', 'fizz-buzz.c')


def test_construct_bash_launcher():
    linker, library_path, executable = '../lib/ld-linux.so.2', '../lib/', 'grep'
    script_content = construct_bash_launcher(linker=linker, library_path=library_path,
                                             executable=executable)
    assert script_content.startswith('#! /bin/bash\n')
    assert linker in script_content
    assert executable in script_content


@pytest.mark.parametrize('compiler', ['diet', 'musl'])
def test_compile(compiler):
    with open(fizz_buzz_source_file, 'r') as f:
        code = f.read()
    compile = compile_diet if compiler == 'diet' else None
    compile = compile or (compile_musl if compiler == 'musl' else None)
    try:
        content = compile(code)
    except CompilerNotFoundError:
        # We'll that's a bummer, but better to test these when the are available than
        # to not test them at all.
        return

    f, filename = tempfile.mkstemp()
    os.close(f)
    with open(filename, 'wb') as f:
        f.write(content)
    st = os.stat(filename)
    os.chmod(f.name, st.st_mode | stat.S_IXUSR)

    process = Popen(f.name, stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()
    assert 'FIZZBUZZ' in stdout.decode('utf-8')
    assert len(stderr.decode('utf-8')) == 0


def test_find_executable():
    original_environment = os.environ.get('PATH')
    original_parent_directory = launchers.parent_directory

    root_directory = create_unpackaged_bundle(
        rename=[], executables=[echo_args_glibc_32], chroot=chroot)
    try:
        binary_name = os.path.basename(echo_args_glibc_32)
        binary_symlink = os.path.join(root_directory, 'bin', binary_name)
        binary_path = os.path.realpath(binary_symlink)
        # This is a pretend directory, but it doesn't check.
        launchers.parent_directory = os.path.join(os.path.dirname(binary_path), 'somewhere', 'else')
        os.environ['PATH'] = os.path.dirname(echo_args_glibc_32)
        assert find_executable(binary_name, skip_original_for_testing=True) == binary_path, \
            'It should have found the binary path "%s".' % binary_path
    finally:
        launchers.parent_directory = original_parent_directory
        os.environ['PATH'] = original_environment
        assert root_directory.startswith('/tmp/')
        shutil.rmtree(root_directory)
