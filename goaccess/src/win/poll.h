#ifndef _WIN_POLL_H_
#define _WIN_POLL_H_

#include <winsock2.h>
#include <windows.h>

#ifndef POLLIN
#define POLLIN      0x0300
#endif
#ifndef POLLPRI
#define POLLPRI     0x0002
#endif
#ifndef POLLOUT
#define POLLOUT     0x0018
#endif
#ifndef POLLERR
#define POLLERR     0x0001
#endif
#ifndef POLLHUP
#define POLLHUP     0x0002
#endif
#ifndef POLLNVAL
#define POLLNVAL    0x0004
#endif

#ifdef _MSC_VER
struct pollfd {
    SOCKET  fd;
    short   events;
    short   revents;
};
#endif

#ifndef nfds_t
typedef unsigned long nfds_t;
#endif

static inline int poll(struct pollfd *fds, nfds_t nfds, int timeout) {
    return WSAPoll((WSAPOLLFD *)fds, nfds, timeout);
}

#endif
