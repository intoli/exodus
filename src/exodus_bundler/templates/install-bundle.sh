#! /bin/bash

user_directory="${HOME}/.exodus"
if [ "$1" != "--user" ]; then
    output_directory=${1:-/opt/exodus}
    mkdir -p ${output_directory} 2> /dev/null
    if [ ! $? ] || [ ! -w ${output_directory} ] ; then
        echo "You don't have write access to "${output_directory}"."
        read -r -p "Would you like to install in ${user_directory} instead? [Y/n] " response
        if [ -z "${response}" ] || [ "${response:0:1}" == "Y" ] || [ "${response:0:1}" == "y" ]; then
            output_directory="${user_directory}"
        else
            echo "Ok, exiting. You can specify a different installation directory as an argument or run again as root."
            exit 1
        fi
    fi
else
    output_directory=${user_directory}
fi

echo "Installing executable bundle in \"${output_directory}\"..."
mkdir -p ${output_directory} 2> /dev/null

# Actually perform the extraction.
begin_tarball_line=$((1 + $(grep --text --line-number '^BEGIN-TARBALL$' $0 | cut -d ':' -f 1)))
tail -n +$begin_tarball_line "$0" | tar -C "${output_directory}" --strip 1 --no-same-owner --preserve-permissions -zvxf - > /dev/null
if [ $? -eq 0 ]; then
    echo "Successfully installed, be sure to add "${output_directory}/bin" to your \$PATH."
    exit 0
else
    echo "Something went wrong, please send an email to contact@intoli.com with details about the bundle."
    exit 1
fi

# The tarball data will go here.
BEGIN-TARBALL
