#ifndef _WIN_UNISTD_H_
#define _WIN_UNISTD_H_

#ifdef __MINGW32__
#include_next <unistd.h>
#else
#include <io.h>
#include <process.h>
#include <stdlib.h>
#include <windows.h>
#include <errno.h>

#ifndef STDIN_FILENO
#define STDIN_FILENO  0
#endif
#ifndef STDOUT_FILENO
#define STDOUT_FILENO 1
#endif
#ifndef STDERR_FILENO
#define STDERR_FILENO 2
#endif

#ifndef S_IRWXU
#define S_IRWXU 0
#endif
#ifndef S_IRUSR
#define S_IRUSR 0
#endif
#ifndef S_IWUSR
#define S_IWUSR 0
#endif
#ifndef S_IXUSR
#define S_IXUSR 0
#endif
#ifndef S_IRWXG
#define S_IRWXG 0
#endif
#ifndef S_IRGRP
#define S_IRGRP 0
#endif
#ifndef S_IWGRP
#define S_IWGRP 0
#endif
#ifndef S_IXGRP
#define S_IXGRP 0
#endif
#ifndef S_IRWXO
#define S_IRWXO 0
#endif
#ifndef S_IROTH
#define S_IROTH 0
#endif
#ifndef S_IWOTH
#define S_IWOTH 0
#endif
#ifndef S_IXOTH
#define S_IXOTH 0
#endif

#define access       _access
#define dup          _dup
#define dup2         _dup2
#define execv        _execv
#define execve       _execve
#define execvp       _execvp
#define fileno       _fileno
#define ftruncate    _chsize
#define getcwd       _getcwd
#define getpid       _getpid
#define isatty       _isatty
#define lseek        _lseek
#define read         _read
#define rmdir        _rmdir
#define swab         _swab
#define tempnam      _tempnam
#define tmpnam       tmpnam_s
#define unlink       _unlink
#define write        _write
#define chdir        _chdir

#define srandom      srand
#define random       rand

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_MSC_VER)
static inline int close(int fd) {
    if (_get_osfhandle(fd) == (intptr_t)INVALID_HANDLE_VALUE) {
        return closesocket((SOCKET)fd);
    }
    return _close(fd);
}
#endif /* _MSC_VER */

static inline unsigned int sleep(unsigned int seconds) {
    Sleep(seconds * 1000);
    return 0;
}

static inline int usleep(unsigned int useconds) {
    Sleep(useconds / 1000);
    return 0;
}

static inline int fsync(int fd) {
    return _commit(fd);
}

#if !defined(HAVE_GETTIMEOFDAY) || !HAVE_GETTIMEOFDAY
struct timezone {
    int tz_minuteswest;
    int tz_dsttime;
};

static inline int gettimeofday(struct timeval *tv, struct timezone *tz) {
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
    if (tz) {
        TIME_ZONE_INFORMATION tzInfo;
        DWORD ret = GetTimeZoneInformation(&tzInfo);
        tz->tz_minuteswest = (ret != TIME_ZONE_ID_INVALID) ? tzInfo.Bias : 0;
        tz->tz_dsttime = 0;
    }
    return 0;
}
#endif

#ifdef __cplusplus
}
#endif
#endif /* __MINGW32__ */

#if !defined(realpath) && !defined(_WIN_UNISTD_REALPATH_)
#define _WIN_UNISTD_REALPATH_
#include <stdlib.h>
static inline char *win_realpath(const char *path, char *resolved) {
    if (resolved)
        return _fullpath(resolved, path, _MAX_PATH) ? resolved : NULL;
    char *buf = (char *)malloc(_MAX_PATH);
    if (!buf) return NULL;
    if (_fullpath(buf, path, _MAX_PATH))
        return buf;
    free(buf);
    return NULL;
}
#define realpath win_realpath
#endif

#endif
