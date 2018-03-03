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

    strace_mode = lines[0].startswith('execve("')
    if not strace_mode:
        return lines
