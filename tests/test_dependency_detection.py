from exodus_bundler.dependency_detection import detect_dependencies


def test_detect_dependencies():
    dependencies = detect_dependencies('/usr/bin/ls')
    print(dependencies)
    assert any('/usr/bin/ls' in dependency for dependency in dependencies), \
        '`/usr/bin/ls` should have been detected as a dependency for `ls`.'
