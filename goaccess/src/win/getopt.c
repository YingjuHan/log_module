#ifndef __GNUC__
/* Minimal getopt/getopt_long implementation for MSVC */

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

int   optind = 1;
int   opterr = 1;
int   optopt;
char *optarg;

static int optreset = 0;
static int place = 0;

int getopt(int argc, char * const argv[], const char *optstring) {
    const char *oli;

    if (!optstring || *optstring == '\0') return -1;

    if (optreset || place == 0) {
        optreset = 0;
        if (optind >= argc || *(argv[optind]) != '-') {
            place = 0;
            return -1;
        }
        if (*(argv[optind] + 1) == '\0') {
            optind++;
            place = 0;
            return -1;
        }
        if (*(argv[optind] + 1) == '-' && *(argv[optind] + 2) == '\0') {
            optind++;
            place = 0;
            return -1;
        }
        place = 1;
    }

    optopt = *(argv[optind] + place);
    place++;

    if (optopt == '\0' || *(argv[optind] + place) == '\0') {
        place = 0;
        optind++;
    }

    if (optopt == ':') {
        if (opterr)
            fprintf(stderr, "%s: option requires an argument -- '%c'\n", argv[0], optopt);
        return ':';
    }

    oli = strchr(optstring, optopt);
    if (oli == NULL) {
        if (opterr)
            fprintf(stderr, "%s: illegal option -- '%c'\n", argv[0], optopt);
        return '?';
    }

    if (*(oli + 1) == ':') {
        if (*(argv[optind] + place) != '\0') {
            optarg = (char *)(argv[optind] + place);
            place = 0;
            optind++;
        } else {
            place = 0;
            optind++;
            if (optind >= argc) {
                if (opterr)
                    fprintf(stderr, "%s: option requires an argument -- '%c'\n", argv[0], optopt);
                return ':';
            }
            optarg = (char *)argv[optind];
            optind++;
        }
    }

    return optopt;
}

int getopt_long(int argc, char * const argv[], const char *optstring,
                const struct option *longopts, int *longindex) {
    int i, matchlen, match;
    const char *p;

    if (optind >= argc) return -1;

    if (argv[optind][0] != '-') return -1;

    if (argv[optind][0] == '-' && argv[optind][1] == '\0') {
        optind++;
        return -1;
    }

    if (argv[optind][0] == '-' && argv[optind][1] == '-' && argv[optind][2] == '\0') {
        optind++;
        return -1;
    }

    if (argv[optind][0] == '-' && argv[optind][1] != '-') {
        return getopt(argc, argv, optstring);
    }

    /* Long option */
    p = argv[optind] + 2;
    match = -1;
    matchlen = -1;

    for (i = 0; longopts[i].name != NULL; i++) {
        const char *optname = longopts[i].name;
        size_t nmlen = strlen(optname);
        size_t arglen = strcspn(p, "=");

        if (arglen == nmlen && strncmp(p, optname, nmlen) == 0) {
            if (match != -1) {
                if (opterr)
                    fprintf(stderr, "%s: option '%s' is ambiguous\n", argv[0], argv[optind]);
                return '?';
            }
            match = i;
            matchlen = (int)arglen;
        }
    }

    if (match == -1) {
        if (opterr)
            fprintf(stderr, "%s: unrecognized option '%s'\n", argv[0], argv[optind]);
        return '?';
    }

    if (longindex) *longindex = match;

    if (*(p + matchlen) == '=') {
        if (longopts[match].has_arg == 0) {
            if (opterr)
                fprintf(stderr, "%s: option '%s' doesn't allow an argument\n", argv[0], longopts[match].name);
            return '?';
        }
        optarg = (char *)(p + matchlen + 1);
    } else if (longopts[match].has_arg == 1) {
        optind++;
        if (optind >= argc) {
            if (opterr)
                fprintf(stderr, "%s: option '%s' requires an argument\n", argv[0], longopts[match].name);
            return ':';
        }
        optarg = (char *)argv[optind];
    } else {
        optarg = NULL;
    }

    optind++;

    if (longopts[match].flag) {
        *(longopts[match].flag) = longopts[match].val;
        return 0;
    }

    return longopts[match].val;
}
#endif /* __GNUC__ */
