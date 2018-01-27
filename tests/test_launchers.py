from exodus.launchers import construct_bash_launcher


def test_construct_bash_launcher():
    linker, binary = 'ld-linux.so.2', 'grep'
    script_content = construct_bash_launcher(linker=linker, binary=binary)
    assert script_content.startswith('#! /bin/bash\n')
    assert linker in script_content
    assert binary in script_content
    assert False, script_content
