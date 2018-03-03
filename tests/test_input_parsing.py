import os

from exodus_bundler.input_parsing import extract_exec_path
from exodus_bundler.input_parsing import extract_paths


parent_directory = os.path.dirname(os.path.realpath(__file__))
strace_output_directory = os.path.join(parent_directory, 'data', 'strace-output')
exodus_strace = os.path.join(strace_output_directory, 'exodus-output.txt')


def test_extract_exec_path():
    line = 'execve("/usr/bin/ls", ["ls"], 0x7ffea775ad70 /* 113 vars */) = 0'
    assert extract_exec_path(line) == '/usr/bin/ls', \
        'It should have extracted the path to the ls executable.'
    assert extract_exec_path('blah') is None, \
        'It should return `None` when there is no match.'


def test_extract_no_paths():
    input_paths = extract_paths('')
    assert input_paths == [], 'It should return an empty list.'


def test_extract_raw_paths():
    input_paths = [
        '/absolute/path/to/file',
        './relative/path',
        '/another/absolute/path',
    ]
    input_paths_with_whitespace = \
        ['  ', ''] + [input_paths[0]] + [' '] + input_paths[1:]
    input_content = '\n'.join(input_paths_with_whitespace)
    extracted_paths = extract_paths(input_content)
    assert set(input_paths) == set(extracted_paths), \
        'The paths should have been extracted without the whitespace.'

def test_extract_strace_paths():
    with open(exodus_strace, 'r') as f:
        content = f.read()
    extracted_paths = extract_paths(content)
    expected_paths = [
        # `execve()` call
        '/home/sangaline/projects/exodus/.env/bin/exodus',
    ]

    for path in expected_paths:
        assert path in extracted_paths, \
            '"%s" should be present in the extracted paths.' % path
