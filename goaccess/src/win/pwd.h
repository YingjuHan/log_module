#ifndef _WIN_PWD_H_
#define _WIN_PWD_H_

#ifdef __cplusplus
extern "C" {
#endif

typedef unsigned int uid_t;

struct passwd {
    char   *pw_name;
    char   *pw_passwd;
    uid_t   pw_uid;
    gid_t   pw_gid;
    char   *pw_gecos;
    char   *pw_dir;
    char   *pw_shell;
};

static inline struct passwd *getpwnam(const char *name) {
    (void)name;
    return NULL;
}

static inline int setuid(uid_t uid) {
    (void)uid;
    return 0;
}

#ifdef __cplusplus
}
#endif

#endif
