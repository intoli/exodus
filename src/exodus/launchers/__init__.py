"""Methods to produce launchers that will invoke the relocated executables with
the proper linker and library paths."""
import os

from exodus.templating import render_template_file


parent_directory = os.path.dirname(os.path.realpath(__file__))
bash_launcher_filename = os.path.join(parent_directory, 'launcher.sh')
c_launcher_filename = os.path.join(parent_directory, 'launcher.c')


def construct_bash_launcher(linker, binary):
    return render_template_file(bash_launcher_filename, linker=linker, binary=binary)
