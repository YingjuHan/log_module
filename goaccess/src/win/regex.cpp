#include "regex.h"
#include <cstring>
#include <new>
#include <regex>
#include <string>

struct RegexHolder {
    std::regex re;
    explicit RegexHolder(const std::string& pattern, std::regex::flag_type flags)
        : re(pattern, flags) {}
};

int regcomp(regex_t *preg, const char *regex, int cflags) {
    if (!preg || !regex) return REG_BADPAT;

    try {
        std::regex::flag_type flags = std::regex::ECMAScript;
        if (cflags & REG_ICASE)  flags |= std::regex::icase;
        if (cflags & REG_EXTENDED) flags |= std::regex::extended;

        void *buf = operator new(sizeof(RegexHolder));
        RegexHolder *holder = new (buf) RegexHolder(regex, flags);
        preg->__internal = holder;
        preg->re_nsub = holder->re.mark_count();
        preg->__flags = cflags;
        return 0;
    } catch (const std::regex_error&) {
        return REG_BADPAT;
    } catch (const std::bad_alloc&) {
        return REG_ESPACE;
    }
}

int regexec(const regex_t *preg, const char *string, size_t nmatch,
            regmatch_t pmatch[], int eflags) {
    if (!preg || !preg->__internal || !string) return REG_BADPAT;
    (void)eflags;

    RegexHolder *holder = static_cast<RegexHolder *>(preg->__internal);
    std::cmatch m;

    try {
        if (!std::regex_search(string, m, holder->re)) {
            return REG_NOMATCH;
        }

        if (pmatch && nmatch > 0) {
            size_t count = m.size();
            for (size_t i = 0; i < nmatch; i++) {
                if (i < count && m[i].matched) {
                    pmatch[i].rm_so = (int)(m[i].first - string);
                    pmatch[i].rm_eo = (int)(m[i].second - string);
                } else {
                    pmatch[i].rm_so = -1;
                    pmatch[i].rm_eo = -1;
                }
            }
        }
        return 0;
    } catch (const std::exception&) {
        return REG_BADPAT;
    }
}

size_t regerror(int errcode, const regex_t *preg, char *errbuf, size_t errbuf_size) {
    (void)preg;
    const char *msg;
    switch (errcode) {
        case REG_NOMATCH: msg = "No match"; break;
        case REG_BADPAT:  msg = "Invalid regex pattern"; break;
        case REG_ESPACE:  msg = "Out of memory"; break;
        case REG_ERANGE:  msg = "Regex range error"; break;
        case REG_ESIZE:   msg = "Regex too large"; break;
        default:          msg = "Unknown regex error"; break;
    }
    size_t len = strlen(msg) + 1;
    if (errbuf && errbuf_size > 0) {
        strncpy(errbuf, msg, errbuf_size - 1);
        errbuf[errbuf_size - 1] = '\0';
    }
    return len;
}

void regfree(regex_t *preg) {
    if (preg && preg->__internal) {
        RegexHolder *holder = static_cast<RegexHolder *>(preg->__internal);
        holder->~RegexHolder();
        operator delete(holder);
        preg->__internal = nullptr;
    }
}
