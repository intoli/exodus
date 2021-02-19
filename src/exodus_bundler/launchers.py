# -*- coding: utf-8 -*-
"""Methods to produce launchers that will invoke the relocated executables with
the proper linker and library paths."""
import os
import re
import tempfile
from distutils.spawn import find_executable as find_executable_original
from subprocess import PIPE
from subprocess import Popen

from exodus_bundler.templating import render_template_file


parent_directory = os.path.dirname(os.path.realpath(__file__))


class CompilerNotFoundError(Exception):
    pass


# This is kind of a hack to find things in PATH inside of bundles.
def find_executable(binary_name, skip_original_for_testing=False):
    # This won't be set on Alpine Linux, but it's required for the `find_executable()` calls.
    if 'PATH' not in os.environ:
        os.environ['PATH'] = '/bin/:/usr/bin/'
    executable = find_executable_original(binary_name)
    if executable and not skip_original_for_testing:
        return executable
    # Try to find it within the same bundle if it's not actually in the PATH.
    directory = parent_directory
    while True:
        directory, basename = os.path.split(directory)
        if not len(basename):
            break
        # The bundle directory.
        if re.match('[A-Fa-f0-9]{64}', basename):
            for bin_directory in os.environ['PATH'].split(':'):
                if os.path.isabs(bin_directory):
                    bin_directory = os.path.relpath(bin_directory, '/')
                candidate_executable = os.path.join(directory, basename,
                                                    bin_directory, binary_name)
                if os.path.exists(candidate_executable):
                    return candidate_executable


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
    f, input_filename = tempfile.mkstemp(prefix='exodus-bundle-', suffix='.c')
    os.close(f)
    f, output_filename = tempfile.mkstemp(prefix='exodus-bundle-')
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


def construct_bash_launcher(linker, library_path, executable, full_linker=True):
    linker_dirname, linker_basename = os.path.split(linker)
    full_linker = 'true' if full_linker else 'false'
    return render_template_file('launcher.sh', linker_basename=linker_basename,
                                linker_dirname=linker_dirname, library_path=library_path,
                                executable=executable, full_linker=full_linker)


def construct_binary_launcher(linker, library_path, executable, full_linker=True):
    linker_dirname, linker_basename = os.path.split(linker)
    full_linker = '1' if full_linker else '0'
    code = render_template_file('launcher.c', linker_basename=linker_basename,
                                linker_dirname=linker_dirname, library_path=library_path,
                                executable=executable, full_linker=full_linker)
    return compile(code)
