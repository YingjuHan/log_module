#ifndef _WIN_NETINET_IN_H_
#define _WIN_NETINET_IN_H_

#include <winsock2.h>
#include <windows.h>

#ifndef IPPROTO_IP
#define IPPROTO_IP   0
#endif
#ifndef IPPROTO_TCP
#define IPPROTO_TCP  6
#endif
#ifndef IPPROTO_UDP
#define IPPROTO_UDP 17
#endif

#ifndef INET6_ADDRSTRLEN
#define INET6_ADDRSTRLEN 46
#endif

#endif
