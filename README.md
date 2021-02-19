<h1 vertical-align="middle">Exodus
    <a targe="_blank" href="https://twitter.com/home?status=Exodus%20%E2%80%93%20Painless%20relocation%20of%20Linux%20binaries%20without%20containers!%20%40IntoliNow%0A%0Ahttps%3A//github.com/intoli/exodus">
        <img height="26px" src="https://simplesharebuttons.com/images/somacro/twitter.png"
            alt="Tweet"></a>
    <a target="_blank" href="https://www.facebook.com/sharer/sharer.php?u=https%3A//github.com/intoli/exodus">
        <img height="26px" src="https://simplesharebuttons.com/images/somacro/facebook.png"
            alt="Share on Facebook"></a>
    <a target="_blank" href="http://reddit.com/submit?url=https%3A%2F%2Fgithub.com%2Fintoli%2Fexodus&title=Exodus%20-%20Painless%20relocation%20of%20ELF%20binaries%20on%20Linux">
        <img height="26px" src="https://simplesharebuttons.com/images/somacro/reddit.png"
            alt="Share on Reddit"></a>
    <a target="_blank" href="https://news.ycombinator.com/submitlink?u=https://github.com/intoli/exodus&t=Exodus%20%E2%80%93%20Painless%20relocation%20of%20Linux%20binaries%20without%20containers">
        <img height="26px" src="media/ycombinator.png"
            alt="Share on Hacker News"></a>
</h1>

<p align="left">
    <a href="https://circleci.com/gh/intoli/exodus/tree/master">
        <img src="https://img.shields.io/circleci/project/github/intoli/exodus/master.svg"
            alt="Build Status"></a>
    <a href="https://circleci.intoli.com/artifacts/intoli/exodus/coverage-report/index.html">
        <img src="https://img.shields.io/badge/dynamic/json.svg?label=coverage&colorB=ff69b4&query=$.coverage&uri=https://circleci.intoli.com/artifacts/intoli/exodus/coverage-report/total-coverage.json"
          alt="Coverage"></a>
    <a href="https://github.com/intoli/exodus/blob/master/LICENSE.md">
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
- [Known Limitations](#known-limitations) - Situations that are currently outside the scope of what exodus can handle.
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

You can try to install these libraries manually, or to relocate them and set `LD_LIBRARY_PATH` to wherever you put them, but it turns out that the locations of the [ld-linux](https://linux.die.net/man/8/ld-linux) linker and the [glibc](https://www.gnu.org/software/libc/) libraries are hardcoded.
Things can very quickly turn into a mess of relocation errors,

```
aria2c: relocation error: /lib/libpthread.so.0: symbol __getrlimit, version
GLIBC_PRIVATE not defined in file libc.so.6 with link time reference
```

segmentation faults,

```
Segmentation fault (core dumped)
```

or, if you're really unlucky, this very confusing symptom of a missing linker.

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


### Optional/Recommended Dependencies

It is also highly recommended that you install [gcc](https://gcc.gnu.org/) and one of either [musl libc](https://www.musl-libc.org/) or [diet libc](https://www.fefe.de/dietlibc/) on the machine where you'll be packaging binaries.
If present, these small C libraries will be used to compile small statically linked launchers for the bundled applications.
An equivalent shell script will be used as a fallback, but it carries significant overhead compared to the compiled launchers.


## Usage

### Command-Line Interface

The command-line interface supports the following options.

```
usage: exodus [-h] [-c CHROOT_PATH] [-a DEPENDENCY] [-d] [--no-symlink FILE]
              [-o OUTPUT_FILE] [-q] [-r [NEW_NAME]] [--shell-launchers] [-t]
              [-v]
              EXECUTABLE [EXECUTABLE ...]

Bundle ELF binary executables with all of their runtime dependencies so that
they can be relocated to other systems with incompatible system libraries.

positional arguments:
  EXECUTABLE            One or more ELF executables to include in the exodus
                        bundle.

optional arguments:
  -h, --help            show this help message and exit
  -c CHROOT_PATH, --chroot CHROOT_PATH
                        A directory that will be treated as the root during
                        linking. Useful for testing and bundling extracted
                        packages that won run without a chroot. (default:
                        None)
  -a DEPENDENCY, --add DEPENDENCY, --additional-file DEPENDENCY
                        Specifies an additional file to include in the bundle,
                        useful for adding programatically loaded libraries and
                        other non-library dependencies. The argument can be
                        used more than once to include multiple files, and
                        directories will be included recursively. (default:
                        [])
  -d, --detect          Attempt to autodetect direct dependencies using the
                        system package manager. Operating system support is
                        limited. (default: False)
  --no-symlink FILE     Signifies that a file must not be symlinked to the
                        deduplicated data directory. This is useful if a file
                        looks for other resources based on paths relative its
                        own location. This is enabled by default for
                        executables. (default: [])
  -o OUTPUT_FILE, --output OUTPUT_FILE
                        The file where the bundle will be written out to. The
                        extension depends on the output type. The
                        "{{executables}}" and "{{extension}}" template strings
                        can be used in the provided filename. If omitted, the
                        output will go to stdout when it is being piped, or to
                        "./exodus-{{executables}}-bundle.{{extension}}"
                        otherwise. (default: None)
  -q, --quiet           Suppress warning messages. (default: False)
  -r [NEW_NAME], --rename [NEW_NAME]
                        Renames the binary executable(s) before packaging. The
                        order of rename tags must match the order of
                        positional executable arguments. (default: [])
  --shell-launchers     Force the use of shell launchers instead of attempting
                        to compile statically linked ones. (default: False)
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

#### Explicitly Adding Extra Files

Additional files can be added to bundles in a number of different ways.
If there is a specific file or directory that you would like to include, then you can use the `--add` option.
For example, the following command will bundle `nmap` and include the contents of `/usr/share/nmap` in the bundle.

```bash
exodus --add /usr/share/nmap nmap
```

You can also pipe a list of dependencies into `exodus`.
This allows you to use standard Linux utilities to find and filter dependencies as you see fit.
The following command sequence uses `find` to include all of the Lua scripts under `/usr/share/nmap`.

```bash
find /usr/share/nmap/ -iname '*.lua' | exodus nmap
```

These two approaches can be used together, and the `--add` flag can also be used multiple times in one command.


#### Auto-Detecting Extra Files

If you're not sure which extra dependencies are necessary, you can use the `--detect` option to query your system's package manager and automatically include any files in the corresponding packages.
Running

```bash
exodus --detect nmap
```

will include the contents of `/usr/share/nmap` as well as its man pages and the contents of `/usr/share/zenmap/`.
If you ever try to relocate a binary that doesn't work with the default configuration, the `--detect` option is a good first thing to try.

You can also pipe the output of `strace` into `exodus` and all of the files that are accessed will be automatically included.
This is particularly useful in situations where shared libraries are loaded programmatically, but it can also be used to determine which files are necessary to run a specific command.
The following command will determine all of the files that `nmap` accesses while running the set of default scripts.

```bash
strace -f nmap --script default 127.0.0.1 2>&1 | exodus nmap
```

The output of `strace` is then parsed by `exodus` and all of the files are included.
It's generally more robust to use `--detect` to find the non-library dependencies, but the `strace` pattern can be indispensable when a program uses `dlopen()` to load libraries programmatically.
Also, note that *any* files that a program accesses will be included in a bundle when following this approach.
Never distribute a bundle without being certain that you haven't accidentally included a file that you don't want to make public.


#### Renaming Binaries

Multiple binaries that have the same name can be installed in parallel through the use of the `--rename`/`-r` option.
Say that you have two different versions of `grep` on your local machine: one at `/bin/grep` and one at `/usr/local/bin/grep`.
In that situation, using the `-r` flag allows you to assign aliases for each binary.

```bash
exodus -r grep-1 -r grep-2 /bin/grep /usr/local/bin/grep
```

The above command would install the two `grep` versions in parallel with `/bin/grep` called `grep-1` and `/usr/local/bin/grep` called `grep-2`.


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


#### Adding to a Docker Image

Tarball formatted exodus bundles can easily be included in Docker images by using the [ADD](https://docs.docker.com/engine/reference/builder/#add) instruction.
You must first create a bundle using the `--tarball` option

```bash
# Create and enter a directory for the Docker image.
mkdir jq
cd jq

# Generate the `exodus-jq-bundle.tgz` bundle.
exodus --tarball jq
```

and then create a `Dockerfile` file inside of the `jq` directory with the following contents.

```
FROM scratch
ADD exodus-jq-bundle.tgz /opt/
ENTRYPOINT ["/opt/exodus/bin/jq"]
```

The Docker image can then be built by running

```bash
docker build -t jq .
```

and `jq` can be run inside of the container.

```bash
docker run jq
```

This simple image will include only the `jq` binary and dependencies, but the bundles can be included in existing docker images in the same way.
For example, adding

```bash
ENV PATH="/opt/exodus/bin:${PATH}"
ADD exodus-jq-bundle.tgz /opt/
```

to an existing `Dockerfile` will make the `jq` binary available for use inside the container.


## How It Works

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
We can explore the structure of the `grep` bundle by using [tree](https://linux.die.net/man/1/tree) combined with a `sed` one-liner to truncate long SHA-256 hashes to 8 digits.
Running

```bash
alias truncate-hashes="sed -r 's/([a-f0-9]{8})[a-f0-9]{56}/\1.../g'"
tree ~/.exodus/ | truncate-hashes
```

will show us all of the files and folders included in the `grep` bundle.

```
/home/sangaline/.exodus/
├── bin
│   └── grep -> ../bundles/3124cd96.../usr/bin/grep
├── bundles
│   └── 3124cd96...
│       ├── lib64
│       │   └── ld-linux-x86-64.so.2 -> ../../../data/dfd5de26...
│       └── usr
│           ├── bin
│           │   ├── grep
│           │   ├── grep-x -> ../../../../data/7477c1a7...
│           │   └── linker-dfd5de26...
│           └── lib
│               ├── libc.so.6 -> ../../../../data/6d0e1d45...
│               ├── libpcre.so.1 -> ../../../../data/a0862ebc...
│               └── libpthread.so.0 -> ../../../../data/85cb56a5...
└── data
    ├── 6d0e1d45...
    ├── 7477c1a7...
    ├── 85cb56a5...
    ├── a0862ebc...
    └── dfd5de26...

8 directories, 13 files
```

You can see that there are three top-level directories within `~/.exodus/`: `bin`, `bundles`, and `data`.
Let's cover these in reverse-alphabetical order, starting with the `data` directory.

The `data` directory contains the actual files from the bundles with names corresponding to SHA-256 hashes of their content.
This is done so that multiple versions of a file with the same filename can be extracted in the `data` directory without overwriting each other.
On the other hand, files that do have the same content *will* overwrite each other.
This avoids the need to store multiple copies of the same data, even if the identical files appear in different bundles or directories.

Next, we have the `bundles` directory, which is full of subfolders that also have SHA-256 hashes as names.
The hashes this time are determined based on the combined directory structure and content of everything included in the bundle.
The hash provides a unique fingerprint for the bundle and allows multiple bundles to be extracted without their directory contents mixing.

Inside of each bundle subdirectory, the original directory structure of the bundle's contents on the host machine is mirrored.
For this particular `grep` bundle, there are `lib64`, `usr/bin`, and `usr/lib` directories.
A more complicated bundle could include additional files from `/usr/share`, `/opt/local`, a user's home directory, or really anywhere on the system (see the `--add` and `--detect` options).
The files in both `lib64` and `usr/lib` simply consist of symlinks to the actual library files in the top-level `data/` directory.
The `usr/bin` directory is a little more complicated.

The `grep` file isn't actually the original `grep` binary, it's a special executable that `exodus` constructs called a "launcher."
A launcher is a tiny program that invokes the linker and overrides the library search path in such a way that our original binary can run without any system libraries being used and causing issues due to incompatibilities.
The linker in this case is the `linker-dfd5de26...` file.
This is located in the same directory so that resource paths can be resolved relative to the running executable.
Finally, the `grep-x` symlink points to the actual `grep` binary that was bundled and extracted in the top-level `data/` directory (this is the ELF file that the linker interprets).

When a C compiler and either [musl libc](https://www.musl-libc.org/) or [diet libc](https://www.fefe.de/dietlibc/) are available, exodus will compile a statically linked binary launcher.
If neither of these are present, it will fall back to using a shell script to perform the task of the launcher.
This adds a little bit of overhead relative to the binary launchers, but they are helpful for understanding what the launchers do.
Here's the shell script version of the `grep-launcher`, for example.

```bash
#! /bin/bash

current_directory="$(dirname "$(readlink -f "$0")")"
executable="${current_directory}/./grep-x"
library_path="../../lib64:../lib64:../../lib:../lib:../../lib32:../lib32"
library_path="${current_directory}/${library_path//:/:${current_directory}/}"
linker="${current_directory}/./linker-dfd5de2638cea087685b67786050dcdc33aac7b67f5f8c2753b7da538517880a"
exec "${linker}" --library-path "${library_path}" --inhibit-rpath "" "${executable}" "$@"
```

You can see that the launcher first constructs the full paths for all of the `LD_LIBRARY_PATH` directories, the executable, and the linker based on its own location.
It then executes the linker with a set of arguments that allow it to search the proper library directories, ignore the hardcoded `RPATH`, and run the binary with any command-line arguments passed along.
This serves a similar purpose to something like [patchelf](https://github.com/NixOS/patchelf) that would modify the `INTERP` and `RPATH` of the binary, but it additionally allows for both the linker and library locations to be specified based *solely on their relative locations*.
This is what allows for the exodus bundles to be extracted in `~/.exodus`, `/opt/exodus/`, or any other location, as long as the internal bundle structure is preserved.

Continuing on with our reverse-alphabetical order, we finally get to the top-level `bin` directory.
The top-level `bin` directory consists of symlinks of the binary names to their corresponding launchers.
This allows for the addition of a single directory to a user's `PATH` variable in order to make the migrated exodus binaries accessible.
For example, adding `export PATH="~/.exodus/bin:${PATH}"` to a `~/.bashrc` file will add all of these entry points to a user's `PATH` and allow them to be run without specifying their full path.


## Known Limitations

There are several scenarios under which bundling an application with exodus will fail.
Many of these are things that we're working on and hope to improve in the future, but some are fundamentally by design and are unlikely to change.
Here you can see an overview of situations where exodus will not be able to successfully relocate executables.

- **Non-ELF Binaries** - Exodus currently only supports completely bundling ELF binaries.
    Interpreted executable files, like shell scripts, can be included in bundles, but their shebang interpreter directives will not be changed.
    This generally means that they will be interpreted using the system version of `bash`, `python`, `perl`, or whatever else.
    The problem that exodus aims to solve is largely centered around the dynamic linking of ELF binaries, so this is unlikely to change in the foreseeable future.
- **Incompatible CPU Architectures** - Binaries compiled for one CPU architecture will generally not be able to run on a CPU of another architecture.
    There are some exceptions to this, for example x64 processors are backwards compatible with x86 instruction sets, but you will not be able to migrate x64 binaries to an x86 or an ARM machine.
    Doing so would require processor emulation, and this is definitely outside the scope of the exodus project.
    If you find yourself looking for a solution to this problem, then you might want to check out [QEMU](https://www.qemu.org/).
- **Incompatible Glibc and Kernel Versions** - When glibc is compiled, it is configured to target a specific kernel version.
    Trying to run any software that was compiled against glibc on a system using an older kernel version than glibc's target version will result in a `FATAL: kernel too old` error.
    You can check the oldest supported kernel version for a binary by running `file /path/to/binary`.
    The output should include a string like `for GNU/Linux 2.6.32` which signifies the oldest kernel version that the binary is compatible with.
    As a workaround, you can create exodus bundles in a Docker image using an operating system image which supports older kernels (*e.g.* use an outdated version of the operating system).
- **Driver Dependent Libraries** - Unlike some other application bundlers, exodus aims to include all of the required libraries when the bundle is created and to completely isolate the transported binary from the destination machine's system libraries.
    This means that any libraries which are compiled for specific hardware drivers will only work on machines with the same drivers.
    A key example of this is the `libGLX_indirect.so` library which can link to either `libGLX_mesa.so` or `libGLX_nvidia.so` depending on which graphics card drivers are used on a given system.
    Bundling dependencies that are not locally available on the source machine is fundamentally outside the scope of what exodus is designed to do, and this will never change.


## Development

The development environment can be setup by running the following.

```bash
# Clone the repository.
git clone https://github.com/intoli/exodus.git
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

Contributions are welcome, but please follow these contributor guidelines outlined in [CONTRIBUTING.md](CONTRIBUTING.md).


## License

Exodus is licensed under a [BSD 2-Clause License](LICENSE.md) and is copyright [Intoli, LLC](https://intoli.com).
