#ifndef _WIN_STRPTIME_H
#define _WIN_STRPTIME_H

#ifdef __cplusplus
extern "C" {
#endif

char *strptime(const char *buf, const char *fmt, struct tm *tm);

#ifdef __cplusplus
}
#endif

#endif
