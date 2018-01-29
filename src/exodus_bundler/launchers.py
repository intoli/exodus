"""Methods to produce launchers that will invoke the relocated executables with
the proper linker and library paths."""
import os
import tempfile
from distutils.spawn import find_executable
from subprocess import PIPE
from subprocess import Popen

from exodus_bundler.templating import render_template_file


class CompilerNotFoundError(Exception):
    pass


def compile(code):
    try:
        return compile_musl(code)
    except CompilerNotFoundError:
        try:
            return compile_diet(code)
        except CompilerNotFoundError:
            raise CompilerNotFoundError('No suiteable C compiler was found.')


def compile_diet(code):
    diet = find_executable('diet')
    gcc = find_executable('gcc')
    if diet is None or gcc is None:
        raise CompilerNotFoundError('The diet compiler was not found.')
    return compile_helper(code, [diet, 'gcc'])


def compile_helper(code, initial_args):
    f, input_filename = tempfile.mkstemp(suffix='.c')
    os.close(f)
    f, output_filename = tempfile.mkstemp()
    os.close(f)
    try:
        with open(input_filename, 'w') as input_file:
            input_file.write(code)

        args = initial_args + ['-static', '-O3', input_filename, '-o', output_filename]
        process = Popen(args, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        assert process.returncode == 0, \
            'There was an error compiling: %s' % stderr.decode('utf-8')

        with open(output_filename, 'rb') as output_file:
            return output_file.read()
    finally:
        os.remove(input_filename)
        os.remove(output_filename)


def compile_musl(code):
    musl = find_executable('musl-gcc')
    if musl is None:
        raise CompilerNotFoundError('The musl compiler was not found.')
    return compile_helper(code, [musl])


def construct_bash_launcher(linker, binary):
    return render_template_file('launcher.sh', linker=linker, binary=binary)


def construct_binary_launcher(linker, binary):
    code = render_template_file('launcher.c', linker=linker, binary=binary)
    return compile(code)
