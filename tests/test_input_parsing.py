import os

from exodus_bundler.input_parsing import extract_exec_filename
from exodus_bundler.input_parsing import extract_filenames


parent_directory = os.path.dirname(os.path.realpath(__file__))
strace_output_directory = os.path.join(parent_directory, 'data', 'strace-output')
exodus_strace = os.path.join(strace_output_directory, 'exodus-output.txt')


def test_extract_exec_filename():
    line = 'execve("/usr/bin/ls", ["ls"], 0x7ffea775ad70 /* 113 vars */) = 0'
    assert extract_exec_filename(line) == '/usr/bin/ls', \
        'It should have extracted the path to the ls executable.'
    assert extract_exec_filename('blah') is None, \
        'It should return `None` when there is no match.'


def test_extract_no_filenames():
    input_filenames = extract_filenames('')
    assert input_filenames == [], 'It should return an empty list.'


def test_extract_raw_filenames():
    input_filenames = [
        '/absolute/path/to/file',
        './relative/path',
        '/another/absolute/path',
    ]
    input_filenames_with_whitespace = \
        ['  ', ''] + [input_filenames[0]] + [' '] + input_filenames[1:]
    input_content = '\n'.join(input_filenames_with_whitespace)
    extracted_filenames = extract_filenames(input_content)
    assert set(input_filenames) == set(extracted_filenames), \
        'The filenames should have been extracted without the whitespace.'

def test_extract_strace_filenames():
    with open(exodus_strace, 'r') as f:
        content = f.read()
    extracted_filenames = extract_filenames(content)
    expected_filenames = [
        # `execve()` call
        '/home/sangaline/projects/exodus/.env/bin/exodus',
    ]

    for filename in expected_filenames:
        assert filename in extracted_filenames, \
            '"%s" should be present in the extracted filenames.' % filename
