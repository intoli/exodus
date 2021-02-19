# -*- coding: utf-8 -*-
import os
import re
import subprocess

from exodus_bundler.launchers import find_executable


class PackageManager(object):
    """Base class representing a package manager.

    The class level attributes can be overwritten in derived classes to customize the behavior.

    Attributes:
        cache_directory (str): The location of the system's package cache.
        list_command (:obj:`list` of :obj:`str`): The command and arguments to list the
            dependencies of a package .
        list_regex (str): A regex to extract the file path from a single line of the output of the
            list command.
        owner_command (:obj:`owner` of :obj:`str`): The command and arguments to determine the
            package that owns a specific file.
        owner_regex (str): A regex to extract the package name from the output of the owner command.
    """
    cache_directory = None
    list_command = None
    list_regex = '(.*)'
    owner_command = None
    owner_regex = '(.*)'

    def find_dependencies(self, path):
        """Finds a list of all of the files contained with the package containing a file."""
        owner = self.find_owner(path)
        if not owner:
            return None

        args = self.list_command + [owner]
        process = subprocess.Popen(args, stdout=subprocess.PIPE)
        stdout, stderr = process.communicate()
        dependencies = []
        for line in stdout.decode('utf-8').split('\n'):
            match = re.search(self.list_regex, line.strip())
            if match:
                dependency_path = match.groups()[0]
                if os.path.exists(dependency_path) and not os.path.isdir(dependency_path):
                    dependencies.append(dependency_path)

        return dependencies

    def find_owner(self, path):
        """Finds the package that owns the specified file path."""
        if not self.cache_exists or not self.commands_exist:
            return None
        args = self.owner_command + [path]
        env = os.environ.copy()
        env['LC_ALL'] = 'C'
        process = subprocess.Popen(args, stdout=subprocess.PIPE, env=env)
        stdout, stderr = process.communicate()
        output = stdout.decode('utf-8').strip()
        match = re.search(self.owner_regex, output)
        if match:
            return match.groups()[0].strip()

    @property
    def cache_exists(self):
        """Whether or not the expected package cache directory exists."""
        return os.path.exists(self.cache_directory) and os.path.isdir(self.cache_directory)

    @property
    def commands_exist(self):
        """Whether or not the list and owner package manager commands can be resolved."""
        commands = {self.list_command[0], self.owner_command[0]}
        return all(find_executable(command) is not None for command in commands)


class Apt(PackageManager):
    cache_directory = '/var/cache/apt'
    list_command = ['dpkg-query', '-L']
    list_regex = '(.+)'
    owner_command = ['dpkg', '-S']
    owner_regex = '(.+): '


class Pacman(PackageManager):
    cache_directory = '/var/cache/pacman'
    list_command = ['pacman', '-Ql']
    list_regex = r'.*\s+(\/.+)'
    owner_command = ['pacman', '-Qo']
    owner_regex = r' is owned by (.*)\s+.*'


class Yum(PackageManager):
    cache_directory = '/var/cache/yum'
    list_command = ['rpm', '-ql']
    list_regex = r'(.+)'
    owner_command = ['rpm', '-qf']
    owner_regex = r'(.+)'


package_managers = [
    Apt(),
    Pacman(),
    Yum(),
]


def detect_dependencies(path):
    # We'll go through the supported systems one by one.
    for package_manager in package_managers:
        dependencies = package_manager.find_dependencies(path)
        if dependencies:
            return dependencies

    return None
