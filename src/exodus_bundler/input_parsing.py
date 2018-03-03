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


def extract_exec_filename(line):
    """Parse a line of strace output and returns the file being executed."""
    for method in exec_methods:
        prefix = method + '("'
        if line.startswith(prefix):
            line = line[len(prefix):]
            parts = line.split('", ')
            if len(parts) > 1:
                return parts[0]
    return None


def extract_filenames(content):
    """Parses filenames from a piped input.

    Args:
        content (str): The raw input, can be either a list of files,
            or the output of the strace command.
    Returns:
        A list of filenames.
    """
    lines = [line.strip() for line in content.splitlines() if len(line.strip())]
    if not len(lines):
        return lines

    # The strace output will start with the exec call of its argument.
    strace_mode = extract_exec_filename(lines[0]) is not None
    if not strace_mode:
        return lines
