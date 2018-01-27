import argparse
import logging
import sys

from exodus import root_logger


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

    parser.add_argument('executable', metavar='EXECUTABLE', nargs='+', help=(
        'One or more ELF executables to include in the exodus bundle.'
    ))

    parser.add_argument('--ldd', metavar='LDD_SCRIPT', default='ldd', help=(
        'The linker that will be invoked to resolve dependencies. In advanced usage, '
        'you may want to write your own `ldd` script which invokes the linker with '
        'custom arguments.'
    ))

    parser.add_argument('-o', '--output', metavar='OUTPUT_FILE',
        default='./exodus-{{executables}}-bundle.{{extension}}',
        help=(
            'The file where the bundle will be written out to. The extension depends on the '
            'output type. The "{{executables}}" and "{{extension}}" template strings can be '
            ' used in the provided filename.'
        ),
    )

    parser.add_argument('-q', '--quiet', action='store_true', help=(
        'Suppress warning messages.'
    ))

    parser.add_argument('-r', '--rename', metavar='NEW_NAME', nargs=1, action='append',
        default=[], help=(
            'Renames the binary executable(s) before packaging. The order of rename tags must '
            'match the order of positional executable arguments.'
        ),
    )

    parser.add_argument('-t', '--tarball', action='store_true', help=(
        'Creates a tarball for manual extraction instead of an installation script. '
        'Note that this will change the output extension from ".sh" to ".tgz".'
    ))

    parser.add_argument('-v', '--verbose', action='store_true', help=(
        'Output additional informational messages.'
    ))

    return vars(parser.parse_args(args, namespace))


def configure_logging(quiet, verbose):
    # Set the level.
    log_level = logging.WARN
    if quiet and not verbose:
        log_level = logging.ERROR
    elif verbose and not quiet:
        log_level = logging.INFO
    root_logger.setLevel(log_level)

    class StdoutFilter(logging.Filter):
        def filter(self, record):
            return record.levelno in (logging.DEBUG, logging.INFO)

    stdout_formatter = logging.Formatter('%(message)s')
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(stdout_formatter)
    stdout_handler.addFilter(StdoutFilter())
    root_logger.addHandler(stdout_handler)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_formatter = logging.Formatter('%(levelname)s: %(message)s')
    stderr_handler.setFormatter(stderr_formatter)
    root_logger.addHandler(stderr_handler)


def main(args=None, namespace=None):
    args = parse_args(args, namespace)

    # Handle the CLI specific options here, removing them from `args` in the process.
    configure_logging(quiet=args.pop('quiet'), verbose=args.pop('verbose'))
