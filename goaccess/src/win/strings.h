#ifndef _WIN_STRINGS_H_
#define _WIN_STRINGS_H_

#include <string.h>

#ifndef HAVE_STRCASECMP
#if defined(_MSC_VER)
#define strcasecmp  _stricmp
#define strncasecmp _strnicmp
#endif
#endif

#ifndef HAVE_STRDUP
#if defined(_MSC_VER)
#define strdup _strdup
#endif
#endif

#endif
