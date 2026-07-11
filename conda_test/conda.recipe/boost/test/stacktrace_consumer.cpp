#include <boost/stacktrace.hpp>
#include <boost/version.hpp>

static_assert(BOOST_VERSION == 106800, "Boost 1.68.0 is required");

int main() {
    const boost::stacktrace::stacktrace trace;
    return trace.empty() ? 0 : 0;
}
