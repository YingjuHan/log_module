#include "cae_console_printer.h"

#include <spdlog/async.h>
#include <spdlog/sinks/stdout_color_sinks.h>

namespace cae
{
namespace detail
{

    //=======================================================================
    // function : ConsolePrinter::ConsolePrinter
    // purpose  :
    //=======================================================================
    ConsolePrinter::ConsolePrinter(LoggerOptions theOptions) : myOptions(std::move(theOptions))
    {
        if (myOptions.thread_model == ThreadModel::SingleThread)
        {
            mySink = std::make_shared<spdlog::sinks::stdout_color_sink_st>();
        }
        else
        {
            mySink = std::make_shared<spdlog::sinks::stdout_color_sink_mt>();
        }
    }

    //=======================================================================
    // function : ConsolePrinter::write
    // purpose  :
    //=======================================================================
    void ConsolePrinter::write(const LogRecord& theRecord)
    {
        get_or_create(theRecord.component)->log(to_spdlog_level(theRecord.level), format_log_message(theRecord));
    }

    //=======================================================================
    // function : ConsolePrinter::flush
    // purpose  :
    //=======================================================================
    void ConsolePrinter::flush()
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        for (const auto& aLoggerEntry : myLoggers)
        {
            aLoggerEntry.second->flush();
        }
    }

    //=======================================================================
    // function : ConsolePrinter::close
    // purpose  :
    //=======================================================================
    void ConsolePrinter::close()
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        myLoggers.clear();
    }

    //=======================================================================
    // function : ConsolePrinter::reload_options
    // purpose  :
    //=======================================================================
    void ConsolePrinter::reload_options(const LoggerOptions& theOptions)
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        myOptions = theOptions;
        for (const auto& aLoggerEntry : myLoggers)
        {
            apply_logger_options(aLoggerEntry.second, myOptions);
        }
    }

    //=======================================================================
    // function : ConsolePrinter::get_or_create
    // purpose  :
    //=======================================================================
    std::shared_ptr<spdlog::logger> ConsolePrinter::get_or_create(const std::string& theModule)
    {
        const std::string           aLoggerName = theModule.empty() ? "default" : theModule;
        std::lock_guard<std::mutex> aLock(myMutex);
        const auto                  anIt = myLoggers.find(aLoggerName);
        if (anIt != myLoggers.end())
        {
            return anIt->second;
        }

        auto aLogger = make_logger(aLoggerName, myOptions, {mySink});
        myLoggers[aLoggerName] = aLogger;
        return aLogger;
    }

    //=======================================================================
    // function : ConsolePrinter::make_logger
    // purpose  :
    //=======================================================================
    std::shared_ptr<spdlog::logger> ConsolePrinter::make_logger(const std::string&                   theName,
                                                                const LoggerOptions&                 theOptions,
                                                                const std::vector<spdlog::sink_ptr>& theSinks)
    {
        std::shared_ptr<spdlog::logger> aLogger;
        if (theOptions.io_mode == IOMode::Async)
        {
            aLogger = std::make_shared<spdlog::async_logger>(theName,
                                                             theSinks.begin(),
                                                             theSinks.end(),
                                                             spdlog::thread_pool(),
                                                             to_spdlog_overflow_policy(
                                                                 theOptions.async_overflow_policy));
        }
        else
        {
            aLogger = std::make_shared<spdlog::logger>(theName, theSinks.begin(), theSinks.end());
        }

        apply_logger_options(aLogger, theOptions);
        return aLogger;
    }

} // namespace detail
} // namespace cae
