import os
import subprocess

from exodus_bundler.bundling import resolve_binary


def detect_dependencies(path):
    # We'll go through the supported systems one by one.
    dependencies = detect_arch_dependencies(path)
    if dependencies:
        return dependencies

    return None


def detect_arch_dependencies(path):
    cache_directory = '/var/cache/pacman'
    if not (os.path.exists(cache_directory) and os.path.isdir(cache_directory)):
        return None

    pacman = resolve_binary('pacman')
    if not pacman:
        return None

    process = subprocess.Popen([pacman, '-Qo', path], stdout=subprocess.PIPE)
    stdout, stderr = process.communicate()
    parts = stdout.decode('utf-8').split(' is owned by ')
    if len(parts) != 2:
        return None

    package_name = parts[1].split(' ')[0]
    process = subprocess.Popen([pacman, '-Ql', package_name], stdout=subprocess.PIPE)
    stdout, stderr = process.communicate()
    dependencies = []
    for line in stdout.decode('utf-8').split('\n'):
        prefix = '%s ' % package_name
        if not line.startswith(prefix):
            continue
        dependency_path = line[len(prefix):]
        if os.path.exists(dependency_path):
            dependencies.append(dependency_path)

    return dependencies
