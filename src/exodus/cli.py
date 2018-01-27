from __future__ import print_function

import argparse


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


def main():
    print('This is where the application goes.')
