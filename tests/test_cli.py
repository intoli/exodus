import pytest

from exodus_bundler.bundling import logger
from exodus_bundler.cli import configure_logging
from exodus_bundler.cli import parse_args


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
