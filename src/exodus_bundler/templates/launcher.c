#include <libgen.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char *argv[])  {
    char *original_library_path = "{{library_path}}";
    char *executable = "{{executable}}";
    char *linker_basename = "{{linker_basename}}";
    char *linker_dirname = "{{linker_dirname}}/";

    char buffer[4096] = { 0 };
    if (readlink("/proc/self/exe", buffer, sizeof(buffer) - strlen(linker_basename) - strlen(linker_dirname) - strlen(executable))) {
        // Determine the location of this launcher executable.
        char *current_directory = dirname(buffer);
        int current_directory_length = strlen(current_directory);
        current_directory[current_directory_length++] = '/';
        current_directory[current_directory_length] = '\0';

        // Prefix each segment with the current working directory so it's an absolute path.
        int library_segments = 1;
        for (int i = 0; original_library_path[i]; i++) {
            library_segments += (original_library_path[i] == ':');
        }
        char *library_path = malloc(
            (strlen(original_library_path) + library_segments * strlen(current_directory) + 1) * sizeof(char));
        strcpy(library_path, current_directory);
        int character_offset = current_directory_length;
        for (int i = 0; original_library_path[i]; i++) {
            library_path[character_offset] = original_library_path[i];
            character_offset++;
            if (original_library_path[i] == ':') {
                strcpy(library_path + character_offset, current_directory);
                character_offset += current_directory_length;
            }
        }
        library_path[character_offset] = '\0';

        // Construct an absolute path to the linker.
        char full_linker_path[4096] = { 0 };
        strcpy(full_linker_path, current_directory);
        strcat(full_linker_path, "/");
        strcat(full_linker_path, linker_dirname);
        strcat(full_linker_path, linker_basename);

        // Construct an absolute path to the executable that we're trying to launch.
        char full_executable_path[4096] = { 0 };
        strcpy(full_executable_path, current_directory);
        strcat(full_executable_path, "/");
        strcat(full_executable_path, executable);

        // Construct all of the arguments for the linker.
        char *linker_args[] = { "--library-path", library_path, "--inhibit-rpath", "", full_executable_path };
        char **combined_args = malloc(sizeof(linker_args) + sizeof(char*) * (argc + 1));
        combined_args[0] = linker_basename;
        memcpy(combined_args + 1, linker_args, sizeof(linker_args));
        memcpy(combined_args + (sizeof(linker_args) / sizeof(char*)) + 1, argv + 1, sizeof(char*)*(argc - 1));
        combined_args[((sizeof(linker_args) + sizeof(char*) * (argc + 1)) / sizeof(char*)) - 1] = NULL;

        // Execute the linker.
        execv(full_linker_path, combined_args);
    }
    return 1;
}
