"""Contains a couple of fairly trivial templating methods used for constructing
the loaders and the output filename. Any instances of {{variable_name}} will be
replaced by the corresponding values."""


def render_template(string, **context):
    for key, value in context.items():
        string = string.replace('{{%s}}' % key, value)
    return string


def render_template_file(filename, **context):
    with open(filename, 'r') as f:
        return render_template(f.read(), **context)
