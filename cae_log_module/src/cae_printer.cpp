#include "cae_printer.h"

namespace cae
{
namespace detail
{

    //=======================================================================
    // function : Printer::flush
    // purpose  :
    //=======================================================================
    void Printer::flush()
    {
    }

    //=======================================================================
    // function : Printer::close
    // purpose  :
    //=======================================================================
    void Printer::close()
    {
    }

    //=======================================================================
    // function : Printer::collect_stats
    // purpose  :
    //=======================================================================
    void Printer::collect_stats(LoggerRuntimeStats& theStats) const
    {
        (void)theStats;
    }

    //=======================================================================
    // function : Printer::reload_options
    // purpose  :
    //=======================================================================
    void Printer::reload_options(const LoggerOptions& theOptions)
    {
        (void)theOptions;
    }

    //=======================================================================
    // function : Printer::apply_logger_options
    // purpose  :
    //=======================================================================
    void Printer::apply_logger_options(const std::shared_ptr<spdlog::logger>& theLogger,
                                       const LoggerOptions&                   theOptions)
    {
        theLogger->set_pattern(theOptions.global_pattern);
        theLogger->set_level(to_spdlog_level(theOptions.min_level));
        theLogger->flush_on(to_spdlog_level(theOptions.flush_level));
    }

    //=======================================================================
    // function : Printer::format_log_message
    // purpose  :
    //=======================================================================
    std::string Printer::format_log_message(const LogRecord& theRecord)
    {
        if (!theRecord.call_chain.empty())
        {
            return theRecord.message + "\nCall chain:" + format_call_chain_block(theRecord.call_chain);
        }

        if (theRecord.call_chain_status == "boost_stacktrace_unavailable")
        {
            return theRecord.message + "\nCall chain: unavailable (boost::stacktrace not available).";
        }

        return theRecord.message;
    }

} // namespace detail
} // namespace cae
