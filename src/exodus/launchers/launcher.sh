#! /bin/bash

current_directory="$(dirname "$(readlink -f "$0")")"
lib_directory="${current_directory}/../lib/"
linker="${lib_directory}/{{linker}}"
executable="${current_directory}/{{binary}}"
exec "${linker}" --library-path "${lib_directory}" --inhibit-rpath "" "${executable}" "$@"
