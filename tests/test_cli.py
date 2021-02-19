# -*- coding: utf-8 -*-
import io
import os
import subprocess
import tarfile
import tempfile

import pytest

from exodus_bundler.bundling import logger
from exodus_bundler.cli import configure_logging
from exodus_bundler.cli import parse_args


parent_directory = os.path.dirname(os.path.realpath(__file__))
chroot = os.path.join(parent_directory, 'data', 'binaries', 'chroot')
fizz_buzz_glibc_32 = os.path.join(chroot, 'bin', 'fizz-buzz-glibc-32')
fizz_buzz_glibc_32_exe = os.path.join(chroot, 'bin', 'fizz-buzz-glibc-32-exe')
fizz_buzz_glibc_64 = os.path.join(chroot, 'bin', 'fizz-buzz-glibc-64')
fizz_buzz_musl_64 = os.path.join(chroot, 'bin', 'fizz-buzz-musl-64')


def run_exodus(args, **options):
    options['universal_newlines'] = options.get('universal_newlines', True)

    # Allow specifying content to pipe into stdin, with options['stdin']
    if 'stdin' in options:
        input = options['stdin'].encode('utf-8')
        options['stdin'] = subprocess.PIPE
    else:
        input = None

    process = subprocess.Popen(
        ['exodus'] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
    stdout, stderr = process.communicate(input=input)
    return process.returncode, stdout, stderr


def test_adding_additional_files(capsys):
    args = ['--chroot', chroot, '--output', '-', '--tarball', fizz_buzz_glibc_32]
    stdin = '\n'.join((fizz_buzz_glibc_32_exe, fizz_buzz_glibc_64))
    returncode, stdout, stderr = run_exodus(args, universal_newlines=False, stdin=stdin)
    assert returncode == 0, "Exodus should have exited with a success status code, but didn't."
    stream = io.BytesIO(stdout)
    with tarfile.open(fileobj=stream, mode='r:gz') as f:
        names = f.getnames()
        assert 'exodus/bin/fizz-buzz-glibc-32' in names, stderr
        # These shouldn't be entrypoints, but should be included
        assert 'exodus/bin/fizz-buzz-glibc-32-exe' not in names, stderr
        assert 'exodus/bin/fizz-buzz-glibc-64' not in names, stderr
        assert any(fizz_buzz_glibc_32_exe in name for name in names), stderr
        assert any(fizz_buzz_glibc_64 in name for name in names), stderr


def test_logging_outputs(capsys):
    # There should be no output before configuring the logger.
    logger.error('error')
    out, err = capsys.readouterr()
    print(out, err)
    assert len(out) == len(err) == 0

    # The different levels should be routed separately to stdout/stderr.
    configure_logging(verbose=True, quiet=False)
    logger.debug('debug')
    logger.warning('warn')
    logger.info('info')
    logger.error('error')
    out, err = capsys.readouterr()
    assert all(output in out for output in ('info'))
    assert all(output not in out for output in ('debug', 'warn', 'error'))
    assert all(output in err for output in ('warn', 'error'))
    assert all(output not in err for output in ('info', 'debug'))


def test_missing_binary(capsys):
    # Without the --verbose flag.
    command = 'this-is-almost-definitely-not-going-to-be-a-command-anywhere'
    returncode, stdout, stderr = run_exodus([command])
    assert returncode != 0, 'Running exodus should have failed.'
    assert 'Traceback' not in stderr, 'Traceback should not be included without the --verbose flag.'

    # With the --verbose flag.
    returncode, stdout, stderr = run_exodus(['--verbose', command])
    assert returncode != 0, 'Running exodus should have failed.'
    assert 'Traceback' in stderr, 'Traceback should be included with the --verbose flag.'


def test_required_argument():
    with pytest.raises(SystemExit):
        parse_args([])
    parse_args(['/bin/bash'])


def test_return_type_is_dict():
    assert type(parse_args(['/bin/bash'])) == dict


def test_quiet_and_verbose_flags():
    result = parse_args(['--quiet', '/bin/bash'])
    assert result['quiet'] and not result['verbose']
    result = parse_args(['--verbose', '/bin/bash'])
    assert result['verbose'] and not result['quiet']


def test_writing_bundle_to_disk():
    f, filename = tempfile.mkstemp(suffix='.sh')
    os.close(f)
    args = ['--chroot', chroot, '--output', filename, fizz_buzz_glibc_32]
    try:
        returncode, stdout, stderr = run_exodus(args)
        assert returncode == 0, "Exodus should have exited with a success status code, but didn't."
        with open(filename, 'rb') as f_in:
            first_line = f_in.readline().strip()
        assert first_line == b'#! /bin/bash', stderr
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


def test_writing_bundle_to_stdout():
    args = ['--chroot', chroot, '--output', '-', fizz_buzz_glibc_32]
    returncode, stdout, stderr = run_exodus(args)
    assert returncode == 0, "Exodus should have exited with a success status code, but didn't."
    assert stdout.startswith('#! /bin/sh'), stderr


def test_writing_tarball_to_disk():
    f, filename = tempfile.mkstemp(suffix='.tgz')
    os.close(f)
    args = ['--chroot', chroot, '--output', filename, '--tarball', fizz_buzz_glibc_32]
    try:
        returncode, stdout, stderr = run_exodus(args)
        assert returncode == 0, "Exodus should have exited with a success status code, but didn't."
        assert tarfile.is_tarfile(filename), stderr
        with tarfile.open(filename, mode='r:gz') as f_in:
            assert 'exodus/bin/fizz-buzz-glibc-32' in f_in.getnames()
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


def test_writing_tarball_to_stdout():
    args = ['--chroot', chroot, '--output', '-', '--tarball', fizz_buzz_glibc_32]
    returncode, stdout, stderr = run_exodus(args, universal_newlines=False)
    assert returncode == 0, "Exodus should have exited with a success status code, but didn't."
    stream = io.BytesIO(stdout)
    with tarfile.open(fileobj=stream, mode='r:gz') as f:
        assert 'exodus/bin/fizz-buzz-glibc-32' in f.getnames(), stderr
