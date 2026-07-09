#ifndef _WIN_GRP_H_
#define _WIN_GRP_H_

#ifdef __cplusplus
extern "C" {
#endif

struct group {
    char   *gr_name;
    char   *gr_passwd;
    int     gr_gid;
    char  **gr_mem;
};

static inline struct group *getgrnam(const char *name) {
    (void)name;
    return NULL;
}

static inline int setgid(gid_t gid) {
    (void)gid;
    return 0;
}

static inline int initgroups(const char *user, gid_t group) {
    (void)user;
    (void)group;
    return 0;
}

#ifdef __cplusplus
}
#endif

#endif
