import os

from exodus_bundler.input_parsing import extract_filenames


parent_directory = os.path.dirname(os.path.realpath(__file__))
strace_output_directory = os.path.join(parent_directory, 'data', 'strace-output')
exodus_strace = os.path.join(strace_output_directory, 'exodus-output.txt')


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
