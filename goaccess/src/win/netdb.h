#ifndef _WIN_NETDB_H_
#define _WIN_NETDB_H_

#include <winsock2.h>
#include <windows.h>
#include <ws2tcpip.h>

#ifndef AI_PASSIVE
#define AI_PASSIVE    0x0001
#endif
#ifndef AI_CANONNAME
#define AI_CANONNAME  0x0002
#endif
#ifndef AI_NUMERICHOST
#define AI_NUMERICHOST 0x0004
#endif

#ifndef NI_NUMERICHOST
#define NI_NUMERICHOST 0x0001
#endif
#ifndef NI_NUMERICSERV
#define NI_NUMERICSERV 0x0002
#endif

#ifndef EAI_NONAME
#define EAI_NONAME    -2
#endif
#ifndef EAI_SERVICE
#define EAI_SERVICE   -3
#endif
#ifndef EAI_FAIL
#define EAI_FAIL      -4
#endif

#ifdef _MSC_VER
struct hostent {
    char  *h_name;
    char **h_aliases;
    int    h_addrtype;
    int    h_length;
    char **h_addr_list;
};
#define h_addr h_addr_list[0]

struct servent {
    char  *s_name;
    char **s_aliases;
    int    s_port;
    char  *s_proto;
};

static inline struct hostent *gethostbyname(const char *name) {
    return (struct hostent *)gethostbyname(name);
}

static inline struct hostent *gethostbyaddr(const char *addr, int len, int type) {
    return (struct hostent *)gethostbyaddr(addr, len, type);
}
#endif

#endif
