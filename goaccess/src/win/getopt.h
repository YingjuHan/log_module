#ifndef _WIN_GETOPT_H_
#define _WIN_GETOPT_H_

#ifdef __GNUC__
#undef __GETOPT_H__
#undef __UNISTD_H_SOURCED__
#include_next <getopt.h>
#else
/* This is a minimal getopt_long implementation for MSVC.
   Based on the public domain implementation. */

#ifdef __cplusplus
extern "C" {
#endif

extern int optind;
extern int opterr;
extern int optopt;
extern char *optarg;

struct option {
    const char *name;
    int has_arg;
    int *flag;
    int val;
};

#define no_argument       0
#define required_argument 1
#define optional_argument 2

int getopt(int argc, char * const argv[], const char *optstring);
int getopt_long(int argc, char * const argv[], const char *optstring,
                const struct option *longopts, int *longindex);

#ifdef __cplusplus
}
#endif

#endif /* __GNUC__ */
#endif /* _WIN_GETOPT_H_ */
