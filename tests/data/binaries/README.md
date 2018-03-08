# Test Programs

This is where small test programs and their dependencies can be places for use in tests.
The `chroot/` subdirectory should be treated as the root directory for placement of any runtime dependencies.
The most commonly used test is `fizz-buzz` which can be compiled with `gcc` by running:

```bash
gcc fizz-buzz.c -no-pie -m32 -o ./chroot/bin/fizz-buzz-glibc-32-exe
gcc fizz-buzz.c -m32 -o ./chroot/bin/fizz-buzz-glibc-32
gcc fizz-buzz.c -m64 -o ./chroot/bin/fizz-buzz-glibc-64
```

There is also a musl version which can be compiled similarly with `clang` (`gcc` gives an error for some reason).

```bash
musl-clang fizz-buzz.c -m64 -o ./chroot/bin/fizz-buzz-musl-64
```

Additionally, there are two small utilities for echoing command arguments and the destination of `/proc/self/exe`.
These can be compiled by running

```bash
gcc echo-args.c -m32 -o ./chroot/bin/echo-args-glibc-32
gcc echo-proc-self-exe.c -m32 -o ./chroot/bin/echo-proc-self-exe-glibc-32
```

## Linking

There is a script in [./chroot/bin/ldd](./chroot/bin/ldd) that attempts to invoke the linker with library paths set in such a way that the results would be comparable to running in actual chroot.
The purpose of this is so that these binaries can be transported across systems for testing.


## License

Components of the [GNU C Library (glibc)](https://www.gnu.org/software/libc/) are in included in this subdirectory in a binary form for the purpose of testing dependency resolution.
These are licensed under a mixture of licenses.
The most recent version of the licenses can be found [in the git repository for the project](https://sourceware.org/git/?p=glibc.git;a=blob_plain;f=LICENSES;hb=HEAD).
Additionally, a copy has been duplicated in this directory in [GLIBC-LICENSES](./GLIBC-LICENSES).

Components of the [MUSL C Library](https://www.musl-libc.org/) are similarly included for the same reasons.
These are licensed under [a standard MIT license](https://git.musl-libc.org/cgit/musl/tree/COPYRIGHT).
This copyright notice is reproduced here in [MUSL-COPYRIGHT](MUSL-COPYRIGHT).

Any third-party dependencies that are included here were taken from the [Arch Linux Package Repositories](https://www.archlinux.org/packages/) without modification.
They provide the source code for these packages for GPL compliance, and their offer is passed along here for any GPLed binaries in this test directory.

If you're involved with one of these projects and feel that there's an issue with the licensing or attribution here, please open an issue on the repository and we'll make whatever changes are necessary.
