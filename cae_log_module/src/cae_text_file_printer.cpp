#include "cae_text_file_printer.h"

#include <spdlog/async.h>
#include <spdlog/sinks/basic_file_sink.h>

namespace cae
{
namespace detail
{

    //=======================================================================
    // function : TextFilePrinter::TextFilePrinter
    // purpose  :
    //=======================================================================
    TextFilePrinter::TextFilePrinter(LoggerOptions theOptions) : myOptions(std::move(theOptions))
    {
    }

    //=======================================================================
    // function : TextFilePrinter::write
    // purpose  :
    //=======================================================================
    void TextFilePrinter::write(const LogRecord& theRecord)
    {
        get_or_create(theRecord.component)->log(to_spdlog_level(theRecord.level), format_log_message(theRecord));
    }

    //=======================================================================
    // function : TextFilePrinter::flush
    // purpose  :
    //=======================================================================
    void TextFilePrinter::flush()
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        for (const auto& aLoggerEntry : myLoggers)
        {
            aLoggerEntry.second->flush();
        }
    }

    //=======================================================================
    // function : TextFilePrinter::close
    // purpose  :
    //=======================================================================
    void TextFilePrinter::close()
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        myLoggers.clear();
    }

    //=======================================================================
    // function : TextFilePrinter::reload_options
    // purpose  :
    //=======================================================================
    void TextFilePrinter::reload_options(const LoggerOptions& theOptions)
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        myOptions = theOptions;
        for (const auto& aLoggerEntry : myLoggers)
        {
            apply_logger_options(aLoggerEntry.second, myOptions);
        }
    }

    //=======================================================================
    // function : TextFilePrinter::get_or_create
    // purpose  :
    //=======================================================================
    std::shared_ptr<spdlog::logger> TextFilePrinter::get_or_create(const std::string& theModule)
    {
        const std::string           aLoggerName = theModule.empty() ? "default" : theModule;
        std::lock_guard<std::mutex> aLock(myMutex);
        const auto                  anIt = myLoggers.find(aLoggerName);
        if (anIt != myLoggers.end())
        {
            return anIt->second;
        }

        const fs::path   aFileName = module_log_path(aLoggerName);
        spdlog::sink_ptr aSink;
        if (myOptions.thread_model == ThreadModel::SingleThread)
        {
            aSink = std::make_shared<spdlog::sinks::basic_file_sink_st>(aFileName.string(), myOptions.truncate_file);
        }
        else
        {
            aSink = std::make_shared<spdlog::sinks::basic_file_sink_mt>(aFileName.string(), myOptions.truncate_file);
        }

        std::shared_ptr<spdlog::logger> aLogger;
        if (myOptions.io_mode == IOMode::Async)
        {
            aLogger = std::make_shared<spdlog::async_logger>(aLoggerName,
                                                             aSink,
                                                             spdlog::thread_pool(),
                                                             to_spdlog_overflow_policy(
                                                                 myOptions.async_overflow_policy));
        }
        else
        {
            aLogger = std::make_shared<spdlog::logger>(aLoggerName, aSink);
        }

        apply_logger_options(aLogger, myOptions);
        myLoggers[aLoggerName] = aLogger;
        return aLogger;
    }

    //=======================================================================
    // function : TextFilePrinter::module_log_path
    // purpose  :
    //=======================================================================
    fs::path TextFilePrinter::module_log_path(const std::string& theModule) const
    {
        const std::string aFileName = myOptions.process_model == ProcessModel::MultiProcess
                                        ? fmt::format("{}_pid{}.log", theModule, current_pid())
                                        : fmt::format("{}.log", theModule);
        return fs::path(myOptions.log_dir) / aFileName;
    }

} // namespace detail
} // namespace cae
