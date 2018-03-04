# We don't actually want to include anything in these directories in bundles.
blacklisted_directories = [
    '/dev/',
    '/proc/',
    '/run/',
    '/sys/',
    '/tmp/exodus-bundle-'
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


def extract_paths(content):
    """Parses paths from a piped input.

    Args:
        content (str): The raw input, can be either a list of files,
            or the output of the strace command.
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
    paths = []
    for line in lines:
        path = extract_exec_path(line) or extract_open_path(line)
        if path:
            blacklisted = any(path.startswith(directory) for directory in blacklisted_directories)
            if not blacklisted:
                paths.append(path)

    return paths
