#! /bin/bash

current_directory="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
lib_directory="${current_directory}/../lib/"
linker="${lib_directory}/{{linker}}"
executable="${current_directory}/{{binary}}"
LD_LIBRARY_PATH="/opt/exodus/packages/aria2c/lib" exec "/opt/exodus/packages/aria2c/aria2c" "$@"
exec "${linker}" --library-path "${lib_directory}" --inhinit-rpath "" "${executable}" "$@"
