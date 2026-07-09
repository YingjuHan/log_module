#ifdef _WIN32

#include <ctype.h>
#include <string.h>
#include <time.h>

static const char *month_names[] = {
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
};

static const char *month_abbrev[] = {
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
};

static const char *weekday_names[] = {
  "Sunday", "Monday", "Tuesday", "Wednesday",
  "Thursday", "Friday", "Saturday"
};

static const char *weekday_abbrev[] = {
  "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"
};

static int match_name(const char **buf, const char **names, int count) {
  int i;
  for (i = 0; i < count; i++) {
    size_t len = strlen(names[i]);
    if (strncasecmp(*buf, names[i], len) == 0) {
      *buf += len;
      return i;
    }
  }
  return -1;
}

char *strptime(const char *buf, const char *fmt, struct tm *tm) {
  int neg, val;

  while (*fmt) {
    if (*fmt != '%') {
      if (isspace((unsigned char)*fmt)) {
        while (*buf && isspace((unsigned char)*buf))
          buf++;
      } else {
        if (*buf != *fmt)
          return NULL;
        buf++;
      }
      fmt++;
      continue;
    }
    fmt++;
    if (!*fmt) return NULL;

    switch (*fmt) {
    case '%':
      if (*buf != '%') return NULL;
      buf++;
      break;
    case 'a': case 'A':
      if (match_name(&buf, weekday_abbrev, 7) < 0 &&
          match_name(&buf, weekday_names, 7) < 0)
        return NULL;
      break;
    case 'b': case 'B': case 'h':
      val = match_name(&buf, month_abbrev, 12);
      if (val < 0) val = match_name(&buf, month_names, 12);
      if (val < 0) return NULL;
      tm->tm_mon = val;
      break;
    case 'd': case 'e':
      if (!isdigit((unsigned char)*buf)) return NULL;
      val = 0;
      if (*buf == ' ') { buf++; }
      if (isdigit((unsigned char)*buf)) { val = *buf - '0'; buf++; }
      if (isdigit((unsigned char)*buf)) { val = val * 10 + (*buf - '0'); buf++; }
      if (val < 1 || val > 31) return NULL;
      tm->tm_mday = val;
      break;
    case 'H':
      if (!isdigit((unsigned char)*buf)) return NULL;
      val = (*buf++ - '0') * 10;
      if (!isdigit((unsigned char)*buf)) return NULL;
      val += (*buf++ - '0');
      if (val < 0 || val > 23) return NULL;
      tm->tm_hour = val;
      break;
    case 'm':
      if (!isdigit((unsigned char)*buf)) return NULL;
      val = (*buf++ - '0') * 10;
      if (!isdigit((unsigned char)*buf)) return NULL;
      val += (*buf++ - '0');
      if (val < 1 || val > 12) return NULL;
      tm->tm_mon = val - 1;
      break;
    case 'M':
      if (!isdigit((unsigned char)*buf)) return NULL;
      val = (*buf++ - '0') * 10;
      if (!isdigit((unsigned char)*buf)) return NULL;
      val += (*buf++ - '0');
      if (val < 0 || val > 59) return NULL;
      tm->tm_min = val;
      break;
    case 'S':
      if (!isdigit((unsigned char)*buf)) return NULL;
      val = (*buf++ - '0') * 10;
      if (!isdigit((unsigned char)*buf)) return NULL;
      val += (*buf++ - '0');
      if (val < 0 || val > 61) return NULL;
      tm->tm_sec = val;
      break;
    case 'Y':
      if (!isdigit((unsigned char)*buf)) return NULL;
      val = 0;
      for (int i = 0; i < 4; i++) {
        if (!isdigit((unsigned char)*buf)) return NULL;
        val = val * 10 + (*buf++ - '0');
      }
      tm->tm_year = val - 1900;
      break;
    case 'y':
      if (!isdigit((unsigned char)*buf)) return NULL;
      val = (*buf++ - '0') * 10;
      if (!isdigit((unsigned char)*buf)) return NULL;
      val += (*buf++ - '0');
      if (val < 69) val += 100;
      tm->tm_year = val;
      break;
    case 'z': {
      int hours = 0, mins = 0;
      neg = 0;
      if (*buf == '+') { buf++; }
      else if (*buf == '-') { neg = 1; buf++; }
      else return NULL;
      if (!isdigit((unsigned char)*buf)) return NULL;
      hours = (*buf++ - '0') * 10;
      if (!isdigit((unsigned char)*buf)) return NULL;
      hours += (*buf++ - '0');
      if (*buf == ':') buf++;
      if (!isdigit((unsigned char)*buf)) return NULL;
      mins = (*buf++ - '0') * 10;
      if (!isdigit((unsigned char)*buf)) return NULL;
      mins += (*buf++ - '0');
      if (hours < 0 || hours > 23 || mins < 0 || mins > 59) return NULL;
      /* tm_gmtoff not available on Windows, so skip */
      break;
    }
    case 'Z':
      /* Skip timezone name */
      while (*buf && isupper((unsigned char)*buf)) buf++;
      break;
    case 'p':
      if (strncasecmp(buf, "AM", 2) == 0) {
        buf += 2;
      } else if (strncasecmp(buf, "PM", 2) == 0) {
        buf += 2;
        if (tm->tm_hour < 12) tm->tm_hour += 12;
      } else return NULL;
      break;
    case 'I': {
      if (!isdigit((unsigned char)*buf)) return NULL;
      val = (*buf++ - '0');
      if (isdigit((unsigned char)*buf))
        val = val * 10 + (*buf++ - '0');
      if (val < 1 || val > 12) return NULL;
      tm->tm_hour = val % 12;
      break;
    }
    case 's':
      {
        time_t t = 0;
        while (*buf && isdigit((unsigned char)*buf))
          t = t * 10 + (*buf++ - '0');
        if (t) {
          struct tm *gt = gmtime(&t);
          if (gt) *tm = *gt;
        }
      }
      break;
    default:
      return NULL;
    }
    fmt++;
  }
  return (char *)buf;
}

#endif
