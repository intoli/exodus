# -*- coding: utf-8 -*-
import argparse
import logging
import sys

from exodus_bundler import root_logger
from exodus_bundler.bundling import create_bundle
from exodus_bundler.errors import FatalError
from exodus_bundler.input_parsing import extract_paths


logger = logging.getLogger(__name__)


def parse_args(args=None, namespace=None):
    """Constructs an argument parser and parses the arguments. The default behavior is
    to parse the arguments from `sys.argv`. A dictionary is returned rather than the
    typical namespace produced by `argparse`."""
    formatter = argparse.ArgumentDefaultsHelpFormatter
    parser = argparse.ArgumentParser(formatter_class=formatter, description=(
        'Bundle ELF binary executables with all of their runtime dependencies '
        'so that they can be relocated to other systems with incompatible system '
        'libraries.'
    ))

    parser.add_argument('executables', metavar='EXECUTABLE', nargs='+', help=(
        'One or more ELF executables to include in the exodus bundle.'
    ))

    parser.add_argument('-c', '--chroot', metavar='CHROOT_PATH',
        default=None,
        help=(
            'A directory that will be treated as the root during linking. Useful for testing and '
            'bundling extracted packages that won\t run without a chroot.'
        ),
    )

    parser.add_argument('-a', '--add', '--additional-file', metavar='DEPENDENCY', action='append',
        default=[],
        help=(
            'Specifies an additional file to include in the bundle, useful for adding '
            'programatically loaded libraries and other non-library dependencies. '
            'The argument can be used more than once to include multiple files, and '
            'directories will be included recursively.'
        ),
    )

    parser.add_argument('-d', '--detect', action='store_true', help=(
        'Attempt to autodetect direct dependencies using the system package manager. '
        'Operating system support is limited.'
    ))

    parser.add_argument('--no-symlink', metavar='FILE', action='append',
        default=[],
        help=(
            'Signifies that a file must not be symlinked to the deduplicated data directory. This '
            'is useful if a file looks for other resources based on paths relative its own '
            'location. This is enabled by default for executables.'
        ),
    )

    parser.add_argument('-o', '--output', metavar='OUTPUT_FILE',
        default=None,
        help=(
            'The file where the bundle will be written out to. The extension depends on the '
            'output type. The "{{executables}}" and "{{extension}}" template strings can be '
            ' used in the provided filename. If omitted, the output will go to stdout when '
            'it is being piped, or to "./exodus-{{executables}}-bundle.{{extension}}" otherwise.'
        ),
    )

    parser.add_argument('-q', '--quiet', action='store_true', help=(
        'Suppress warning messages.'
    ))

    parser.add_argument('-r', '--rename', metavar='NEW_NAME', nargs='?', action='append',
        default=[], help=(
            'Renames the binary executable(s) before packaging. The order of rename tags must '
            'match the order of positional executable arguments.'
        ),
    )

    parser.add_argument('--shell-launchers', action='store_true', help=(
        'Force the use of shell launchers instead of attempting to compile statically linked ones.'
    ))

    parser.add_argument('-t', '--tarball', action='store_true', help=(
        'Creates a tarball for manual extraction instead of an installation script. '
        'Note that this will change the output extension from ".sh" to ".tgz".'
    ))

    parser.add_argument('-v', '--verbose', action='store_true', help=(
        'Output additional informational messages.'
    ))

    return vars(parser.parse_args(args, namespace))


def configure_logging(quiet, verbose, suppress_stdout=False):
    # Set the level.
    log_level = logging.WARN
    if quiet and not verbose:
        log_level = logging.ERROR
    elif verbose and not quiet:
        log_level = logging.INFO
    root_logger.setLevel(log_level)

    class StderrFilter(logging.Filter):
        def filter(self, record):
            return record.levelno in (logging.WARN, logging.ERROR)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_formatter = logging.Formatter('%(levelname)s: %(message)s')
    stderr_handler.setFormatter(stderr_formatter)
    stderr_handler.addFilter(StderrFilter())
    root_logger.addHandler(stderr_handler)

    # We won't even configure/add the stdout handler if this is specified.
    if suppress_stdout:
        return

    class StdoutFilter(logging.Filter):
        def filter(self, record):
            return record.levelno in (logging.DEBUG, logging.INFO)

    stdout_formatter = logging.Formatter('%(message)s')
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(stdout_formatter)
    stdout_handler.addFilter(StdoutFilter())
    root_logger.addHandler(stdout_handler)


def main(args=None, namespace=None):
    args = parse_args(args, namespace)

    # Dynamically set the default output to stdout if it is being piped.
    if args['output'] is None:
        if sys.stdout.isatty():
            args['output'] = './exodus-{{executables}}-bundle.{{extension}}'
        else:
            args['output'] = '-'

    # Handle the CLI specific options here, removing them from `args` in the process.
    quiet, verbose = args.pop('quiet'), args.pop('verbose')
    suppress_stdout = args['output'] == '-'
    configure_logging(quiet=quiet, verbose=verbose, suppress_stdout=suppress_stdout)

    # Allow piping in additional files.
    if not sys.stdin.isatty():
        args['add'] += extract_paths(sys.stdin.read())

    # Create the bundle with all of the arguments.
    try:
        create_bundle(**args)
    except FatalError as fatal_error:
        logger.error('Fatal error encountered, exiting.')
        logger.error(fatal_error, exc_info=verbose)
        sys.exit(1)
