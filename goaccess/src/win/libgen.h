#ifndef _WIN_LIBGEN_H_
#define _WIN_LIBGEN_H_

#include <stdlib.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

static inline char *basename(char *path) {
    if (!path || !*path) return ".";
    char *p = path + strlen(path) - 1;
    while (p > path && (*p == '/' || *p == '\\')) p--;
    p[1] = '\0';
    while (p >= path) {
        if (*p == '/' || *p == '\\')
            return p + 1;
        p--;
    }
    return path;
}

static inline char *dirname(char *path) {
    if (!path || !*path) return ".";
    char *p = path + strlen(path) - 1;
    while (p > path && (*p == '/' || *p == '\\')) p--;
    while (p >= path) {
        if (*p == '/' || *p == '\\') {
            if (p == path) {
                path[1] = '\0';
                return path;
            }
            *p = '\0';
            return path;
        }
        p--;
    }
    return ".";
}

#ifdef __cplusplus
}
#endif

#endif
