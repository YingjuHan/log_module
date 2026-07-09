#ifndef _WIN_SYS_TIME_H_
#define _WIN_SYS_TIME_H_

#include <winsock2.h>
#include <windows.h>

#include <time.h>

#ifndef HAVE_STRUCT_TIMEVAL
#define HAVE_STRUCT_TIMEVAL 1
#endif

#ifdef __cplusplus
extern "C" {
#endif

static inline int gettimeofday(struct timeval *tv, void *tz) {
    if (tv) {
        FILETIME ft;
        unsigned __int64 t;
        GetSystemTimeAsFileTime(&ft);
        t = ((unsigned __int64)ft.dwHighDateTime << 32) | ft.dwLowDateTime;
        t /= 10;
        t -= 11644473600000000ULL;
        tv->tv_sec  = (long)(t / 1000000UL);
        tv->tv_usec = (long)(t % 1000000UL);
    }
    return 0;
}

#ifdef __cplusplus
}
#endif

#endif
