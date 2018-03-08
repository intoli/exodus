#include <stdio.h>
#include <unistd.h>

int main(void) {
    char buffer[4096];
    readlink("/proc/self/exe", buffer, sizeof(buffer) - 1);
    printf("%s\n", buffer);
    return 0;
}
