"""Contains a couple of fairly trivial templating methods used for constructing
the loaders and the output filename. Any instances of {{variable_name}} will be
replaced by the corresponding values."""

import os


parent_directory = os.path.dirname(os.path.realpath(__file__))
template_directory = os.path.join(parent_directory, 'templates')


# This is kind of a hack to make the templates accessible using bbfreeze.
grandparent_basename = os.path.basename(os.path.dirname(parent_directory))
if grandparent_basename == 'library.zip' and not os.path.exists(template_directory):
    template_directory = os.path.normpath(os.path.join(parent_directory, '..', '..', 'templates'))


def render_template(string, **context):
    for key, value in context.items():
        string = string.replace('{{%s}}' % key, value)
    return string


def render_template_file(filename, **context):
    if not os.path.isabs(filename):
        filename = os.path.join(template_directory, filename)
    with open(filename, 'r') as f:
        return render_template(f.read(), **context)
