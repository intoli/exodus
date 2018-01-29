import os
import stat
import tempfile
from subprocess import PIPE
from subprocess import Popen

import pytest

from exodus_bundler.launchers import CompilerNotFoundError
from exodus_bundler.launchers import compile_diet
from exodus_bundler.launchers import compile_musl
from exodus_bundler.launchers import construct_bash_launcher


parent_directory = os.path.dirname(os.path.realpath(__file__))
fizz_buzz_source_file = os.path.join(parent_directory, 'data', 'binaries', 'fizz-buzz.c')


def test_construct_bash_launcher():
    linker, binary = 'ld-linux.so.2', 'grep'
    script_content = construct_bash_launcher(linker=linker, binary=binary)
    assert script_content.startswith('#! /bin/bash\n')
    assert linker in script_content
    assert binary in script_content


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
