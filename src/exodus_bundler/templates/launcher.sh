#! /bin/bash

current_directory="$(dirname "$(readlink -f "$0")")"
executable="${current_directory}/{{executable}}"
library_path="{{library_path}}"
library_path="${current_directory}/${library_path//:/:${current_directory}/}"
linker="${current_directory}/{{linker_dirname}}/{{linker_basename}}"
if [ "{{full_linker}}" == "true" ]; then
    exec "${linker}" --library-path "${library_path}" --inhibit-rpath "" "${executable}" "$@"
else
    exec "${linker}" --library-path "${library_path}" "${executable}" "$@"
fi
