#ifndef _WIN_SYS_WAIT_H_
#define _WIN_SYS_WAIT_H_

#include <process.h>

#define WNOHANG  1
#define WUNTRACED 2

#define WIFEXITED(status)   (((status) & 0xFF) == 0)
#define WEXITSTATUS(status) (((status) >> 8) & 0xFF)
#define WIFSIGNALED(status) (((status) & 0xFF) != 0)
#define WTERMSIG(status)    ((status) & 0x7F)
#define WIFSTOPPED(status)  (((status) & 0xFF) == 0x7F)
#define WSTOPSIG(status)    (((status) >> 8) & 0xFF)

#endif
