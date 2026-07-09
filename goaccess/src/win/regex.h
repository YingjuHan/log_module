#ifndef _WIN_REGEX_H_
#define _WIN_REGEX_H_

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    size_t re_nsub;
    void *__internal;
    int __flags;
} regex_t;

typedef struct {
    int rm_so;
    int rm_eo;
} regmatch_t;

#define REG_EXTENDED 1
#define REG_ICASE    2
#define REG_NOSUB    4
#define REG_NOMATCH  1
#define REG_BADPAT   2
#define REG_ESPACE   3
#define REG_ERANGE   4
#define REG_ESIZE    5

int regcomp(regex_t *preg, const char *regex, int cflags);
int regexec(const regex_t *preg, const char *string, size_t nmatch, regmatch_t pmatch[], int eflags);
size_t regerror(int errcode, const regex_t *preg, char *errbuf, size_t errbuf_size);
void regfree(regex_t *preg);

#ifdef __cplusplus
}
#endif

#endif
