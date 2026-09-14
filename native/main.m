#import <Cocoa/Cocoa.h>
#import <Carbon/Carbon.h>
#include <signal.h>
#include <unistd.h>

// The wire format is one UTF-8 ID<TAB>name record per line. Remove terminal
// controls here; zsh separately escapes prompt metacharacters before rendering.
static NSString *clean(NSString *value) {
    if (!value) return @"";
    NSCharacterSet *controls = [NSCharacterSet controlCharacterSet];
    return [[value componentsSeparatedByCharactersInSet:controls] componentsJoinedByString:@" "];
}

static NSString *record(TISInputSourceRef source) {
    NSString *identifier = (__bridge NSString *)TISGetInputSourceProperty(source, kTISPropertyInputSourceID);
    NSString *name = (__bridge NSString *)TISGetInputSourceProperty(source, kTISPropertyLocalizedName);
    return [NSString stringWithFormat:@"%@\t%@\n", clean(identifier), clean(name ?: identifier)];
}

static NSString *lastRecord;
static void emitCurrent(BOOL force) {
    @autoreleasepool {
        TISInputSourceRef source = TISCopyCurrentKeyboardInputSource();
        if (!source) return;
        NSString *value = record(source);
        CFRelease(source);
        if (!force && [value isEqualToString:lastRecord]) return;
        lastRecord = value;
        if (fputs(value.UTF8String, stdout) == EOF || fflush(stdout) == EOF) exit(0);
    }
}

static void inputSourceChanged(__unused CFNotificationCenterRef center,
                               __unused void *observer, __unused CFStringRef name,
                               __unused const void *object, __unused CFDictionaryRef userInfo) {
    // Distributed CF notifications arrive on the main run loop. Query and
    // flush here instead of adding another NSOperationQueue scheduling hop.
    emitCurrent(NO);
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSString *mode = argc == 2 ? @(argv[1]) : @"";
        if (argc == 2 && [mode isEqualToString:@"--once"]) {
            emitCurrent(YES);
            return lastRecord ? 0 : 1;
        }
        if (argc == 2 && [mode isEqualToString:@"--list"]) {
            NSDictionary *filter = @{(__bridge NSString *)kTISPropertyInputSourceIsSelectCapable: @YES,
                                     (__bridge NSString *)kTISPropertyInputSourceIsEnabled: @YES,
                                     (__bridge NSString *)kTISPropertyInputSourceCategory:
                                         (__bridge NSString *)kTISCategoryKeyboardInputSource};
            NSArray *sources = CFBridgingRelease(TISCreateInputSourceList((__bridge CFDictionaryRef)filter, false));
            for (id source in sources) fputs(record((__bridge TISInputSourceRef)source).UTF8String, stdout);
            return 0;
        }
        if (argc != 2 || ![mode isEqualToString:@"--watch"]) {
            fprintf(stderr, "Usage: which-keyboard --once | --list | --watch\n");
            return 64;
        }

        // SIGUSR1 requests a fresh snapshot when a new command line starts.
        // dispatch sources keep all TIS calls on the main thread.
        signal(SIGUSR1, SIG_IGN);
        dispatch_source_t refresh = dispatch_source_create(DISPATCH_SOURCE_TYPE_SIGNAL, SIGUSR1, 0,
                                                           dispatch_get_main_queue());
        dispatch_source_set_event_handler(refresh, ^{ emitCurrent(YES); });
        dispatch_resume(refresh);

        CFNotificationCenterAddObserver(CFNotificationCenterGetDistributedCenter(), NULL,
                                        inputSourceChanged, kTISNotifySelectedKeyboardInputSourceChanged,
                                        NULL, CFNotificationSuspensionBehaviorDeliverImmediately);

        // Focus changes may restore an application's remembered input source.
        [NSWorkspace.sharedWorkspace.notificationCenter
            addObserverForName:NSWorkspaceDidActivateApplicationNotification
            object:nil queue:NSOperationQueue.mainQueue
            usingBlock:^(__unused NSNotification *notification) {
                emitCurrent(NO);
                dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 100 * NSEC_PER_MSEC),
                               dispatch_get_main_queue(), ^{ emitCurrent(NO); });
            }];

        // Ensure the helper also exits if the shell is killed without running
        // its exit hook. No polling and no global daemon are required.
        dispatch_source_t parent = dispatch_source_create(DISPATCH_SOURCE_TYPE_PROC, getppid(),
                                                          DISPATCH_PROC_EXIT, dispatch_get_main_queue());
        if (parent) {
            dispatch_source_set_event_handler(parent, ^{ exit(0); });
            dispatch_resume(parent);
        }
        emitCurrent(YES);
        CFRunLoopRun();
    }
    return 0;
}
