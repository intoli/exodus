import os
import re
from subprocess import PIPE
from subprocess import Popen


def find_direct_library_dependencies(binary):
    """Finds the libraries that a binary directly links to."""
    return [match.group(1) for match in filter(None,
       (re.search('=>\s*([^(]*?)\s*\(', line) for line in run_ldd(binary)))]


def run_ldd(binary):
    """Runs `ldd` and gets the combined stdout/stderr output as a list of lines."""
    if not os.path.exists(binary):
        raise FileNotFoundError('"%s" is not a file.')
    process = Popen(['ldd', binary], stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()
    return stdout.decode('utf-8').split('\n') + stderr.decode('utf-8').split('\n')
