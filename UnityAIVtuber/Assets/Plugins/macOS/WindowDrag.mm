#import <Foundation/Foundation.h>
#import <Cocoa/Cocoa.h>

extern "C" void MoveMacWindow(int dx, int dy) {
    dispatch_async(dispatch_get_main_queue(), ^{
        NSWindow *window = [NSApp mainWindow];
        if (window) {
            NSRect frame = [window frame];
            frame.origin.x += dx;
            frame.origin.y += dy;
            [window setFrame:frame display:YES animate:NO];
        }
    });
}
