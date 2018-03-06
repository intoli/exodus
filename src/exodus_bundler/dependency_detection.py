import os
import subprocess

from exodus_bundler.bundling import resolve_binary


def detect_dependencies(path):
    # We'll go through the supported systems one by one.
    dependencies = detect_arch_dependencies(path)
    if dependencies:
        return dependencies

    dependencies = detect_debian_dependencies(path)
    if dependencies:
        return dependencies

    dependencies = detect_redhat_dependencies(path)
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


def detect_debian_dependencies(path):
    cache_directory = '/var/cache/apt'
    if not (os.path.exists(cache_directory) and os.path.isdir(cache_directory)):
        return None

    dpkg = resolve_binary('dpkg')
    if not dpkg:
        return None

    process = subprocess.Popen([dpkg, '-S', path], stdout=subprocess.PIPE)
    stdout, stderr = process.communicate()
    parts = stdout.decode('utf-8').split(': ')
    if len(parts) != 2:
        return None

    package_name = parts[0]
    dpkg_query = resolve_binary('dpkg-query')
    if not dpkg_query:
        return None

    package_name = parts[0]
    process = subprocess.Popen([dpkg_query, '-L', package_name], stdout=subprocess.PIPE)
    stdout, stderr = process.communicate()
    dependencies = []
    for dependency_path in stdout.decode('utf-8').split('\n'):
        if os.path.exists(dependency_path):
            dependencies.append(dependency_path)

    return dependencies


def detect_redhat_dependencies(path):
    cache_directory = '/var/cache/yum'
    if not (os.path.exists(cache_directory) and os.path.isdir(cache_directory)):
        return None

    rpm = resolve_binary('rpm')
    if not rpm:
        return None

    process = subprocess.Popen([rpm, '-qf', path], stdout=subprocess.PIPE)
    stdout, stderr = process.communicate()
    package_name = stdout.decode('utf-8').strip()

    process = subprocess.Popen([rpm, '-ql', package_name], stdout=subprocess.PIPE)
    stdout, stderr = process.communicate()
    dependencies = []
    for dependency_path in stdout.decode('utf-8').split('\n'):
        if os.path.exists(dependency_path):
            dependencies.append(dependency_path)

    return dependencies
