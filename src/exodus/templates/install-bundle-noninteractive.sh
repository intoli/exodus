#! /bin/bash

user_directory="${HOME}/.exodus"
output_directory=/opt/exodus
mkdir -p ${output_directory} 2> /dev/null
if [ ! $? ] || [ ! -w ${output_directory} ] ; then
    output_directory=${user_directory}
fi

echo "Installing executable bundle in \"${output_directory}\"..."
mkdir -p ${output_directory} 2> /dev/null

# Actually perform the extraction.
base64 -d << "END_OF_FILE" | tar -C "${output_directory}" --strip 1 --preserve-permissions -zvxf -
{{base64_encoded_tarball}}
END_OF_FILE
if [ $? -eq 0 ]; then
    echo "Successfully installed, be sure to add "${output_directory}/bin" to your \$PATH."
    exit 0
else
    echo "Something went wrong, please send an email to contact@intoli.com with details about the bundle."
    exit 1
fi
