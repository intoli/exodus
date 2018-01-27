# Test Programs

This is where small test programs and their dependencies can be places for use in tests.
The `chroot/` subdirectory should be treated as the root directory for placement of any runtime dependencies.
Currently, the only test is `fizz-buzz` which can be compiled with `musl` by running:

```bash
musl-gcc fizz-buzz.c -o ./chroot/bin/fizz-buzz
```


## License

Components of the `musl` c libraries are in included in this subdirectory in a binary form for the purpose of testing dependency resolution.
These are licensed under an MIT license.
The most recent version of this license and author list can be found [in their git repository for the project](http://git.musl-libc.org/cgit/musl/tree/COPYRIGHT).
Additionally, a copy has been duplicated in this directory in [MUSL-COPYRIGHT](./MUSL-COPYRIGHT).
