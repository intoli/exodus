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
Server-oriented distributions tend to have more limited and outdated packages available, so it's fairly common that one might wish to install a piece of software that they already have installed on their own desktop or laptop.

With exodus, transferring a piece of software that's working on one computer to another is as simple as this.

```bash
exodus aria2c | ssh intoli.com
```

Exodus handles bundling all of the binary's dependencies, compiling a statically linked wrapper for the executable that invokes the relocated linker directly, and installing the bundle in `~/.exodus/` on the remote machine.
You can see it in action here.

![Demonstration of usage with htop](media/htop-demo.gif)


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

## Packaging Format

```bash
tree ~/.exodus/ | sed -r 's/([a-f0-9]{5})[a-f0-9]{59}/\1.../g'
```

```
/home/sangaline/.exodus/
├── bin
│   └── grep -> ../bundles/7477c.../bin/grep-launcher
├── bundles
│   └── 7477c...
│       ├── bin
│       │   ├── grep
│       │   └── grep-launcher
│       └── lib
│           ├── ld-linux-x86-64.so.2 -> ../../../lib/68dd9.../ld-linux-x86-64.so.2
│           ├── libc.so.6 -> ../../../lib/91a11.../libc.so.6
│           ├── libpcre.so.1 -> ../../../lib/a0862.../libpcre.so.1
│           └── libpthread.so.0 -> ../../../lib/55dbf.../libpthread.so.0
└── lib
    ├── 55dbf...
    │   ├── data
    │   └── libpthread.so.0 -> ./data
    ├── 68dd9...
    │   ├── data
    │   └── ld-linux-x86-64.so.2 -> ./data
    ├── 91a11...
    │   ├── data
    │   └── libc.so.6 -> ./data
    └── a0862...
        ├── data
        └── libpcre.so.1 -> ./data

10 directories, 15 files
```


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
