import hashlib
import logging
import os
import re
from subprocess import PIPE
from subprocess import Popen


logger = logging.getLogger(__name__)


def create_bundle(**kwargs):
    logger.error('Not yet implemented.')
    logger.info('Keys: %s' % kwargs.keys())


def find_all_library_dependencies(ldd, binary):
    """Finds all libraries that a binary directly or indirectly links to."""
    all_dependencies = set()
    unprocessed_dependencies = set(find_direct_library_dependencies(ldd, binary))
    while len(unprocessed_dependencies):
        all_dependencies |= unprocessed_dependencies
        new_dependencies = set()
        for dependency in unprocessed_dependencies:
            new_dependencies |= set(find_direct_library_dependencies(ldd, dependency))
        unprocessed_dependencies = new_dependencies - all_dependencies
    return list(all_dependencies)


def find_direct_library_dependencies(ldd, binary):
    """Finds the libraries that a binary directly links to."""
    matches = filter(None, (re.search('=>\s*([^(]*?)\s*\(', line) for line in run_ldd(ldd, binary)))
    return [match.group(1) for match in matches]


def run_ldd(ldd, binary):
    """Runs `ldd` and gets the combined stdout/stderr output as a list of lines."""
    if not os.path.exists(binary):
        raise FileNotFoundError('"%s" is not a file.')
    process = Popen([ldd, binary], stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()
    return stdout.decode('utf-8').split('\n') + stderr.decode('utf-8').split('\n')


def sha256_hash(filename):
    with open(filename, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()
