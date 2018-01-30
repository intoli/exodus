# Exodus

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
