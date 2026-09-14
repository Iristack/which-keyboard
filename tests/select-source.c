// Test-only utility for the opt-in real input-source switch test.
#include <Carbon/Carbon.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

static int select_source(const char *name) {
    CFStringRef identifier = CFStringCreateWithCString(NULL, name, kCFStringEncodingUTF8);
    const void *keys[] = { kTISPropertyInputSourceID };
    const void *values[] = { identifier };
    CFDictionaryRef filter = CFDictionaryCreate(NULL, keys, values, 1,
                                                &kCFTypeDictionaryKeyCallBacks,
                                                &kCFTypeDictionaryValueCallBacks);
    CFArrayRef sources = TISCreateInputSourceList(filter, false);
    OSStatus status = -1;
    if (sources && CFArrayGetCount(sources)) {
        status = TISSelectInputSource((TISInputSourceRef)CFArrayGetValueAtIndex(sources, 0));
    }
    if (sources) CFRelease(sources);
    CFRelease(filter);
    CFRelease(identifier);
    if (status) fprintf(stderr, "TISSelectInputSource failed: %d\n", (int)status);
    return status ? 1 : 0;
}

static double now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}

int main(int argc, char **argv) {
    if (argc != 2) return 64;
    if (strcmp(argv[1], "--interactive")) return select_source(argv[1]);
    char identifier[4096];
    while (fgets(identifier, sizeof(identifier), stdin)) {
        identifier[strcspn(identifier, "\r\n")] = '\0';
        double started = now();
        int status = select_source(identifier);
        printf("%.9f\t%.9f\t%d\n", started, now(), status);
        fflush(stdout);
    }
    return 0;
}
