# Test Programs

This is where small test programs and their dependencies can be places for use in tests.
The `chroot/` subdirectory should be treated as the root directory for placement of any runtime dependencies.
Currently, the only test is `fizz-buzz` which can be compiled with `gcc` by running:

```bash
gcc fizz-buzz.c -m32 -o ./chroot/bin/fizz-buzz
```


## Linking

There is a script in [./chroot/bin/ldd](./chroot/bin/ldd) that attempts to invoke the linker with library paths set in such a way that the results would be comparable to running in actual chroot.
The purpose of this is so that these binaries can be transported across systems for testing.


## License

Components of the [GNU C Library (glibc)](https://www.gnu.org/software/libc/) are in included in this subdirectory in a binary form for the purpose of testing dependency resolution.
These are licensed under a mixture of licenses.
The most recent version of the licenses can be found [in the git repository for the project](https://sourceware.org/git/?p=glibc.git;a=blob_plain;f=LICENSES;hb=HEAD).
Additionally, a copy has been duplicated in this directory in [GLIBC-LICENSES](./GLIBC-LICENSES).
