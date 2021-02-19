# -*- coding: utf-8 -*-
import os

from exodus_bundler.dependency_detection import detect_dependencies


def test_detect_dependencies():
    # This is a little janky, but the test suite won't run anywhere where it's not true.
    ls = '/usr/bin/ls'
    if not os.path.exists(ls):
        ls = '/bin/ls'
    assert os.path.exists(ls), 'This test assumes that `ls` is installed on the system.'

    dependencies = detect_dependencies(ls)
    assert any(ls in dependency for dependency in dependencies), \
        '`%s` should have been detected as a dependency for `ls`.' % ls
