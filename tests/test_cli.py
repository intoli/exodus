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
ldd_path = os.path.join(chroot, 'bin', 'ldd')
fizz_buzz_path = os.path.join(chroot, 'bin', 'fizz-buzz')


def test_logging_outputs(capsys):
    # There should be no output before configuring the logger.
    logger.error('error')
    out, err = capsys.readouterr()
    print(out, err)
    assert len(out) == len(err) == 0

    # The different levels should be routed separately to stdout/stderr.
    configure_logging(verbose=True, quiet=False)
    logger.debug('debug')
    logger.warn('warn')
    logger.info('info')
    logger.error('error')
    out, err = capsys.readouterr()
    assert all(output in out for output in ('info'))
    assert all(output not in out for output in ('debug', 'warn', 'error'))
    assert all(output in err for output in ('warn', 'error'))
    assert all(output not in err for output in ('info', 'debug'))


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


def test_writing_bundle_to_disk(script_runner):
    f, filename = tempfile.mkstemp(suffix='.sh')
    os.close(f)
    args = ['--ldd', ldd_path, '--output', filename, fizz_buzz_path]
    try:
        result = script_runner.run('exodus', *args)
        with open(filename, 'rb') as f_in:
            first_line = f_in.readline().strip()
        assert first_line == b'#! /bin/bash', result.stderr
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


def test_writing_bundle_to_stdout(script_runner):
    args = ['--ldd', ldd_path, '--output', '-', fizz_buzz_path]
    result = script_runner.run('exodus', *args)
    assert result.stdout.startswith('#! /bin/bash'), result.stderr


def test_writing_tarball_to_disk(script_runner):
    f, filename = tempfile.mkstemp(suffix='.tgz')
    os.close(f)
    args = ['--ldd', ldd_path, '--output', filename, '--tarball', fizz_buzz_path]
    try:
        result = script_runner.run('exodus', *args)
        assert tarfile.is_tarfile(filename), result.stderr
        with tarfile.open(filename, mode='r:gz') as f_in:
            assert 'exodus/bin/fizz-buzz' in f_in.getnames()
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


def test_writing_tarball_to_stdout(script_runner):
    args = ['--ldd', ldd_path, '--output', '-', '--tarball', fizz_buzz_path]
    process = subprocess.Popen(['exodus'] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    stream = io.BytesIO(stdout)
    with tarfile.open(fileobj=stream, mode='r:gz') as f:
        assert 'exodus/bin/fizz-buzz' in f.getnames(), stderr
