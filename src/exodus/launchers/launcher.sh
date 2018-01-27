#! /bin/bash

current_directory="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
lib_directory="${current_directory}/../lib/"
linker="${lib_directory}/{{linker}}"
executable="${current_directory}/{{binary}}"
exec "${linker}" --library-path "${lib_directory}" --inhibit-rpath "" "${executable}" "$@"
