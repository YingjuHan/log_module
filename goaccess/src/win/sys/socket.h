#ifndef _WIN_SYS_SOCKET_H_
#define _WIN_SYS_SOCKET_H_

#include <winsock2.h>
#include <windows.h>

#undef EWOULDBLOCK
#undef EINPROGRESS
#undef EALREADY
#undef ENOTSOCK
#undef EDESTADDRREQ
#undef EMSGSIZE
#undef EPROTOTYPE
#undef ENOPROTOOPT
#undef EPROTONOSUPPORT
#undef ESOCKTNOSUPPORT
#undef EOPNOTSUPP
#undef EPFNOSUPPORT
#undef EAFNOSUPPORT
#undef EADDRINUSE
#undef EADDRNOTAVAIL
#undef ENETDOWN
#undef ENETUNREACH
#undef ENETRESET
#undef ECONNABORTED
#undef ECONNRESET
#undef ENOBUFS
#undef EISCONN
#undef ENOTCONN
#undef ESHUTDOWN
#undef ETOOMANYREFS
#undef ETIMEDOUT
#undef ECONNREFUSED
#undef ELOOP
#undef ENAMETOOLONG
#undef EHOSTDOWN
#undef EHOSTUNREACH
#undef ENOTEMPTY
#undef EPROCLIM
#undef EUSERS
#undef EDQUOT
#undef ESTALE
#undef EREMOTE

#include <errno.h>

#ifdef _MSC_VER
typedef SOCKET socklen_t;
#endif

/* POSIX socket constants not in winsock */
#ifndef SHUT_RD
#define SHUT_RD   0
#endif
#ifndef SHUT_WR
#define SHUT_WR   1
#endif
#ifndef SHUT_RDWR
#define SHUT_RDWR 2
#endif

/* SO_* options - winsock2.h has most of these, define any missing */

/* Helper to ensure Winsock is initialized */
static inline int win_socket_startup(void) {
    WSADATA wsa;
    return WSAStartup(MAKEWORD(2, 2), &wsa);
}

static inline int win_socket_cleanup(void) {
    return WSACleanup();
}

#endif
