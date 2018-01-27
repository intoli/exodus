#include <libgen.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char *argv[])  {
    char *ld_filename = "{{linker}}";
    char *executable_filename = "{{binary}}";

    char buffer[2048] = { 0 };
    if (readlink("/proc/self/exe", buffer, sizeof(buffer) - 8 - strlen(ld_filename) - strlen(executable_filename))) {
       char *bin_directory = dirname(buffer);
       char library_directory[2048] = { 0 };
       strcpy(library_directory, bin_directory);
       strcat(library_directory, "/../lib/");

       char full_ld_path[2048] = { 0 };
       strcpy(full_ld_path, library_directory);
       strcat(full_ld_path, ld_filename);

       char full_executable_path[2048] = { 0 };
       strcpy(full_executable_path, bin_directory);
       strcat(full_executable_path, "/");
       strcat(full_executable_path, executable_filename);

       char *ld_args[] = { "--library-path", library_directory, "--inhibit-rpath", "", full_executable_path };
       char **combined_args = malloc(sizeof(ld_args) + sizeof(char*) * (argc + 1));
       combined_args[0] = ld_filename;
       memcpy(combined_args + 1, ld_args, sizeof(ld_args));
       memcpy(combined_args + (sizeof(ld_args) / sizeof(char*)) + 1, argv + 1, sizeof(char*)*(argc - 1));
       combined_args[((sizeof(ld_args) + sizeof(char*) * (argc + 1)) / sizeof(char*)) - 1] = NULL;
       execv(full_ld_path, combined_args);
    }
    return 1;
}
