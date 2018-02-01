<h1 vertical-align="middle">Exodus
    <a targe="_blank" href="https://twitter.com/home?status=Exodus%20makes%20it%20possible%20to%20transport%20binaries%20between%20Linux%20machines%20without%20needing%20to%20worry%20about%20dependencies%20or%20library%20incompatibilities.%20Very%20cool!%0A%0Ahttps%3A//github.com/intoli/exodus">
        <img height="26px" src="https://simplesharebuttons.com/images/somacro/twitter.png"
            alt="Tweet"></a>
    <a target="_blank" href="https://www.facebook.com/sharer/sharer.php?u=https%3A//github.com/intoli/exodus">
        <img height="26px" src="https://simplesharebuttons.com/images/somacro/facebook.png"
            alt="Share on Facebook"></a>
    <a target="_blank" href="http://reddit.com/submit?url=https%3A%2F%2Fgithub.com%2Fintoli%2Fexodus&title=Exodus%20-%20Painless%20relocation%20of%20ELF%20binaries%20on%20Linux">
        <img height="26px" src="https://simplesharebuttons.com/images/somacro/reddit.png"
            alt="Share on Reddit"></a>
</h1>

<p align="left">
    <a href="https://circleci.com/gh/Intoli/exodus/tree/master">
        <img src="https://img.shields.io/circleci/project/github/Intoli/exodus/master.svg"
            alt="Build Status"></a>
    <a href="https://circleci.com/gh/Intoli/exodus/tree/master">
        <img src="https://img.shields.io/badge/coverage-80.83%25-lightgrey.svg"
            alt="Coverage"></a>
    <a href="https://github.com/Intoli/exodus/blob/master/LICENSE.md">
        <img src="https://img.shields.io/pypi/l/exodus-bundler.svg"
            alt="License"></a>
    <a href="https://pypi.python.org/pypi/exodus-bundler/">
        <img src="https://img.shields.io/pypi/v/exodus-bundler.svg"
            alt="PyPI Version"></a>
</p>


Exodus is a tool that makes it easy to successfully relocate Linux ELF binaries from one system to another.
This is useful in situations where you don't have root access on a machine or where a package simply isn't available for a given Linux distribution.
For example, CentOS 6.X and Amazon Linux don't have packages for [Google Chrome](https://www.google.com/chrome/browser/desktop/index.html) or [aria2](https://aria2.github.io/).
Server-oriented distributions tend to have more limited and outdated packages than desktop distributions, so it's fairly common that one might have a piece of software installed on their laptop that they can't easily install on a remote machine.

With exodus, transferring a piece of software that's working on one computer to another is as simple as this.

```bash
exodus aria2c | ssh intoli.com
```

Exodus handles bundling all of the binary's dependencies, compiling a statically linked wrapper for the executable that invokes the relocated linker directly, and installing the bundle in `~/.exodus/` on the remote machine.
You can see it in action here.

![Demonstration of usage with htop](media/htop-demo.gif)


## Table of Contents

- [The Problem Being Solved](#the-problem-being-solved) - An overview of some of the challenges that arise when relocating binaries.
- [Installation](#installation) - Instructions for installing exodus.
- [Usage](#usage)
    - [The Command-Line Interface](#command-line-interface) - The options supported by the command-line utility.
    - [Usage Examples](#examples) - Common usage patterns, helpful for getting started quickly.
- [How It Works](#how-it-works) - An overview of how exodus works.
- [Development](#development) - Instructions for setting up the development environment.
- [Contributing](#contributing) - Guidelines for contributing.
- [License](#license) - License details for the project.


## The Problem Being Solved

If you simply copy an executable file from one system to another, then you're very likely going to run into problems.
Most binaries available on Linux are dynamically linked and depend on a number of external library files.
You'll get an error like this when running a relocated binary when it has a missing dependency.

```
aria2c: error while loading shared libraries: libgnutls.so.30: cannot open shared object file: No such file or directory
```

You can try to install these libraries manually, or to relocate them and manually set `LD_LIBRARY_PATH`, but it turns out that the locations of the [ld-linux](https://linux.die.net/man/8/ld-linux) linker and the [glibc](https://www.gnu.org/software/libc/) libraries are hardcoded.
Things can very quickly turn into a mess of relocation errors,

```
aria2c: relocation error: /lib/libpthread.so.0: symbol __getrlimit, version
GLIBC_PRIVATE not defined in file libc.so.6 with link time reference
```

segmentation faults,

```
Segmentation fault (core dumped)
```

or, if you're really unlucky, this symptom of a missing linker.

```
$ ./aria2c
bash: ./aria2c: No such file or directory
$ ls -lha ./aria2c
-rwxr-xr-x 1 sangaline sangaline 2.8M Jan 30 21:18 ./aria2c
```

Exodus works around these issues by compiling a small statically linked launcher binary that invokes the relocated linker directly with any hardcoded `RPATH` library paths overridden.
The relocated binary will run with the exact same linker and libraries that it ran with on its origin machine.


## Installation

The package can be installed from [the package on pypi](https://pypi.python.org/pypi/exodus_bundler).
Running the following will install `exodus` locally for your current user.

```bash
pip install --user exodus-bundler
```

You will then need to add `~/.local/bin/` to your `PATH` variable in order to run the `exodus` executable (if you haven't already done so).
This can be done by adding

```
export PATH="~/.local/bin/:${PATH}"
```

to your `~/.bashrc` file.

It is also highly recommended that you install [gcc](https://gcc.gnu.org/) and one of either [musl libc](https://www.musl-libc.org/) or [diet libc](https://www.fefe.de/dietlibc/) on the machine where you'll be packaging binaries.
If present, these small C libries will be used to compile small statically linked launchers for the bundled applications.
An equivalent shell script will be used as a fallback, but it carries significant overhead compared to the compiled launchers.


## Usage

### Command-Line Interface

The command-line interface supports the following options.

```
usage: exodus [-h] [--ldd LDD_SCRIPT] [-o OUTPUT_FILE] [-q] [-r NEW_NAME] [-t]
              [-v]
              EXECUTABLE [EXECUTABLE ...]

Bundle ELF binary executables with all of their runtime dependencies so that
they can be relocated to other systems with incompatible system libraries.

positional arguments:
  EXECUTABLE            One or more ELF executables to include in the exodus
                        bundle.

optional arguments:
  -h, --help            show this help message and exit
  --ldd LDD_SCRIPT      The linker that will be invoked to resolve
                        dependencies. In advanced usage, you may want to write
                        your own `ldd` script which invokes the linker with
                        custom arguments. (default: ldd)
  -o OUTPUT_FILE, --output OUTPUT_FILE
                        The file where the bundle will be written out to. The
                        extension depends on the output type. The
                        "{{executables}}" and "{{extension}}" template strings
                        can be used in the provided filename. If ommited, the
                        output will go to stdout when it is being piped, or to
                        "./exodus-{{executables}}-bundle.{{extension}}"
                        otherwise. (default: None)
  -q, --quiet           Suppress warning messages. (default: False)
  -r NEW_NAME, --rename NEW_NAME
                        Renames the binary executable(s) before packaging. The
                        order of rename tags must match the order of
                        positional executable arguments. (default: [])
  -t, --tarball         Creates a tarball for manual extraction instead of an
                        installation script. Note that this will change the
                        output extension from ".sh" to ".tgz". (default:
                        False)
  -v, --verbose         Output additional informational messages. (default:
                        False)
```


### Examples

#### Piping Over SSH

The easiest way to install an executable bundle on a remote machine is to pipe the `exodus` command output over SSH.
For example, the following will install the `aria2c` command on the `intoli.com` server.

```bash
exodus aria2c | ssh intoli.com
```

This requires that the default shell for the remote user be set to `bash` (or a compatible shell).
If you use `csh`, then you need to additionally run `bash` on the remote server like this.

```bash
exodus aria2c | ssh intoli.com bash
```

#### Manual Extraction

You can create a compressed tarball directly instead of the default script by specifying the `--tarball` option.
To create a tarball, copy it to a remote server, and then extract it in `~/custom-location`, you could run the following.

```bash
# Create the tarball.
exodus --tarball aria2c --output aria2c.tgz

# Copy it to the remote server and remove it locally.
scp aria2c.tgz intoli.com:/tmp/aria2c.tgz
rm aria2c.tgz

# Make sure that `~/custom-location` exists.
ssh intoli.com "mkdir -p ~/custom-location"

# Extract the tarball remotely.
ssh intoli.com "tar --strip 1 -C ~/custom-location -zxf /tmp/aria2c.tgz"

# Remove the remote tarball.
ssh intoli.com "rm /tmp/aria2c.tgz"
```

You will additionally need to add `~/custom-location/bin` to your `PATH` variable on the remote server.
This can be done by adding the following to `~/.bashrc` on the remote server.

```bash
export PATH="~/custom-location/bin:${PATH}"
```


## How it Works

There are two main components to how exodus works:

1. Finding and bundling all of a binary's dependencies.

2. Launching the binary in such a way that the proper dependencies are used without any potential interaction from system libraries on the destination machine.

The first component is actually fairly simple.
You can invoke [ld-linux](https://linux.die.net/man/8/ld-linux) with the `LD_TRACE_LOADED_OBJECTS` environment variable set to `1` and it will list all of the resolved library dependencies for a binary.
For example, running

```bash
LD_TRACE_LOADED_OBJECTS=1 /lib64/ld-linux-x86-64.so.2 /bin/grep
```

will output the following.

```
    linux-vdso.so.1 =>  (0x00007ffc7495c000)
    libpcre.so.0 => /lib64/libpcre.so.0 (0x00007f89b2f3e000)
    libc.so.6 => /lib64/libc.so.6 (0x00007f89b2b7a000)
    libpthread.so.0 => /usr/lib/libpthread.so.0 (0x00007f0e95e8c000)
    /lib64/ld-linux-x86-64.so.2 (0x00007f89b3196000)
```

The `linus-vdso.so.1` dependency refers to kernel space routines that are exported to user space, but the other four are shared library files on disk that are required in order to run `grep`.
Notably, one of these dependencies is the `/lib64/ld-linux-x86-64.so.2` linker itself.
The location of this file is typically hardcoded into an ELF binary's `INTERP` header and the linker is invoked by the kernel when you run the program.
We'll come back to that in a minute, but for now the main point is that we can find a binary's direct dependencies using the linker.

Of course, these direct dependencies might have additional dependencies of their own.
We can iteratively find all of the necessary dependencies by following the same approach of invoking the linker again for each of the library dependencies.
This isn't actually necessary for `grep`, but exodus does handle finding the full set of dependencies for you.

After all of the dependencies are found, exodus puts them together with the binary in a tarball that can be extracted (typically into either `/opt/exodus/` or `~/.exodus`).
We can explore the structure of the grep bundle by using [tree](https://linux.die.net/man/1/tree) combined with a `sed` one-liner to truncate long SHA-256 hashes to 8 digits.
Running

```bash
alias truncate-hashes="sed -r 's/([a-f0-9]{8})[a-f0-9]{56}/\1.../g'"
tree ~/.exodus/ | truncate-hashes
```

will show us all of the files and folders included in the `grep` bundle.

```
/home/sangaline/.exodus/
├── bin
│   └── grep -> ../bundles/7477c1a7.../bin/grep-launcher.sh
├── bundles
│   └── 7477c1a7...
│       ├── bin
│       │   ├── grep
│       │   └── grep-launcher.sh
│       └── lib
│           ├── ld-linux-x86-64.so.2 -> ../../../lib/68dd9b50...
│           ├── libc.so.6 -> ../../../lib/91a11344...
│           ├── libpcre.so.1 -> ../../../lib/a0862ebc...
│           └── libpthread.so.0 -> ../../../lib/55dbf3e8...
└── lib
    ├── 55dbf3e8...
    ├── 68dd9b50...
    ├── 91a11344...
    └── a0862ebc...

6 directories, 11 files
```

You can see that there are three top-level directories within `~/.exodus/`: `bin`, `bundles`, and `lib`.
Let's cover these in reverse-alphabetical order, starting with the `lib` directory.

The `lib` directory contains library files whose names correspond to SHA-256 hashes of the libraries that they represent.
This is done so that multiple versions of a library with the same filename can be extracted in the `lib` directory without overwriting each other.
This also means that identical files with different names won't result in multiple copies of the same data.

Next, we have the `bundles` directory, which is full of subfolders with SHA-256 hashes as names.
The hashes this time correspond to the contents of the binary that is being bundled.
The purpose of this is that multiple versions of the same binary can be bundled and extracted without the directory contents mixing.

Inside of each bundle subdirectory, there are two additional subdirectories: `bin` and `lib`.
The `lib` subdirectory simply consists of symlinks to the actual library files in the top-level `lib/` directory.
The `bin` subdirectory consists of the original binary file and a second executable called a "launcher."
Each launcher is a tiny program that invokes the linker and overrides the library search path in such a way that our original binary can run without any system libraries being used and causing issues due to incompatibilities.

When a C compiler and either [musl libc](https://www.musl-libc.org/) or [diet libc](https://www.fefe.de/dietlibc/) are available, exodus will compile a statically linked binary launcher.
If neither of these are present, it will fall back to using a shell script to perform the task of the launcher.
This adds a little bit of overhead relative to the binary launchers, but they are helpful for understanding what the launchers do.
Here's the shell script version of the `grep-launcher`, for example.

```bash
#! /bin/bash

current_directory="$(dirname "$(readlink -f "$0")")"
lib_directory="${current_directory}/../lib/"
linker="${lib_directory}/ld-linux-x86-64.so.2"
executable="${current_directory}/grep"
exec "${linker}" --library-path "${lib_directory}" --inhibit-rpath "" "${executable}" "$@"
```

You can see that the launcher first constructs the full paths for the `lib` directory, the executable, and the linker based on its own location.
It then executes the linker with a set of arguments that allow it to search the proper `lib` directory, ignore the hardcoded `RPATH`, and run the binary with any arguments to the launcher passed along.
This serves a similar purpose to something like [patchelf](https://github.com/NixOS/patchelf) that would modify the `INTERP` and `RPATH` of the binary, but it additionally allows for both the linker and library locations to be specified based *solely on their relative locations*.
This is what allows for the exodus bundles to be extracted in `~/.exodus`, `/opt/exodus/`, or any other location, as long as the internal bundle structure is preserved.

Continuing on with our reverse-alphabetical order, we finally get to the top-level `bin` directory.
The top-level `bin` directory consists of symlinks of the binary names to their corresponding launchers.
This allows for the addition of a single directory to a user's `PATH` variable in order to make the migrated exodus binaries accessible.


## Development

The development environment can be setup by running the following.

```bash
# Clone the repository.
git clone git@github.com:intoli/exodus.git
cd exodus

# Create and enter a virtualenv.
virtualenv .env
. .env/bin/activate

# Install the development requirements.
pip install -r development-requirements.txt

# Install the exodus package in editable mode.
pip install -e .
```

The test suite can then be run using [tox](https://tox.readthedocs.io/en/latest/).

```bash
tox
```

## Contributing

Contributions are welcome, but please create an issue on [the issue tracker](https://github.com/intoli/exodus/issues/new) first to discuss the contribution first.
New feature additions should include tests and it's a requirement that all tests must pass before pull requests are merged.


## License

Exodus is licensed under a [BSD 2-Clause License](LICENSE.md) and is copyright [Intoli, LLC](https://intoli.com).
