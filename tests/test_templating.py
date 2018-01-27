from exodus.templating import render_template


def test_render_template():
    template = '{{greeting}}, my name is {{name}}.'
    expected = 'Hello, my name is Evan.'
    result = render_template(template, greeting='Hello', name='Evan')
    assert expected == result
