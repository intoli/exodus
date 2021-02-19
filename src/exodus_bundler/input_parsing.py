# -*- coding: utf-8 -*-
import os
import re


# We don't actually want to include anything in these directories in bundles.
blacklisted_directories = [
    '/dev/',
    '/proc/',
    '/run/',
    '/sys/',
    # This isn't a directory exactly, but it will filter out active bundling.
    '/tmp/exodus-bundle-',
]

exec_methods = [
    'execve',
    'exec',
    'execl',
    'execlp',
    'execle',
    'execv',
    'execvp',
    'execvpe',
]


def extract_exec_path(line):
    """Parse a line of strace output and returns the file being executed."""
    line = strip_pid_prefix(line)
    for method in exec_methods:
        prefix = method + '("'
        if line.startswith(prefix):
            line = line[len(prefix):]
            parts = line.split('", ')
            if len(parts) > 1:
                return parts[0]
    return None


def extract_open_path(line):
    """Parse a line of strace output and returns the file being opened."""
    line = strip_pid_prefix(line)
    for prefix in ['openat(AT_FDCWD, "', 'open("']:
        if line.startswith(prefix):
            parts = line[len(prefix):].split('", ')
            if len(parts) != 2:
                continue
            if 'ENOENT' in parts[1]:
                continue
            if 'O_RDONLY' not in parts[1]:
                continue
            if 'O_DIRECTORY' in parts[1]:
                continue
            return parts[0]
    return None


def extract_stat_path(line):
    """Parse a line of strace output and return the file that stat was called on."""
    line = strip_pid_prefix(line)
    prefix = 'stat("'
    if line.startswith(prefix):
        parts = line[len(prefix):].split('", ')
        if len(parts) == 2 and 'ENOENT' not in parts[1]:
            return parts[0]
    return None


def extract_paths(content, existing_only=True):
    """Parses paths from a piped input.

    Args:
        content (str): The raw input, can be either a list of files,
            or the output of the strace command.
        existing_only (bool, optional): Requires that files actually exist and aren't directories.
    Returns:
        A list of paths.
    """
    lines = [line.strip() for line in content.splitlines() if len(line.strip())]
    if not len(lines):
        return lines

    # The strace output will start with the exec call of its argument.
    strace_mode = extract_exec_path(lines[0]) is not None
    if not strace_mode:
        return lines

    # Extract files from `open()`, `openat()`, and `exec()` calls.
    paths = set()
    for line in lines:
        path = extract_exec_path(line) or extract_open_path(line) or extract_stat_path(line)
        if path:
            blacklisted = any(path.startswith(directory) for directory in blacklisted_directories)
            if not blacklisted:
                if not existing_only:
                    paths.add(path)
                    continue
                if os.path.exists(path) and os.access(path, os.R_OK) and not os.path.isdir(path):
                    paths.add(path)

    return list(paths)


def strip_pid_prefix(line):
    """Strips out the `[pid XXX] ` prefix if present."""
    match = re.match(r'\[pid\s+\d+\]\s*', line)
    if match:
        return line[len(match.group()):]
    return line
