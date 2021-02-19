# -*- coding: utf-8 -*-
import os

from exodus_bundler.templating import render_template
from exodus_bundler.templating import render_template_file


parent_directory = os.path.dirname(os.path.realpath(__file__))
data_directory = os.path.join(parent_directory, 'data')


def test_render_template():
    template = '{{greeting}}, my name is {{name}}.'
    expected = 'Hello, my name is Evan.'
    result = render_template(template, greeting='Hello', name='Evan')
    assert expected == result


def test_render_template_file():
    template_file = os.path.join(data_directory, 'template.txt')
    result = render_template_file(template_file, noun='word', location='here')
    with open(os.path.join(data_directory, 'template-result.txt'), 'r') as f:
        expected_result = f.read()
    assert result == expected_result
