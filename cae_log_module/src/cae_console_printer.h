#pragma once

#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include "cae_printer.h"

#include <spdlog/spdlog.h>

namespace cae
{
namespace detail
{

    class ConsolePrinter final : public Printer
    {
      public:

        explicit ConsolePrinter(LoggerOptions theOptions);

        void write(const LogRecord& theRecord) override;
        void flush() override;
        void close() override;
        void reload_options(const LoggerOptions& theOptions) override;

      private:

        std::shared_ptr<spdlog::logger>        get_or_create(const std::string& theModule);
        static std::shared_ptr<spdlog::logger> make_logger(const std::string&                   theName,
                                                           const LoggerOptions&                 theOptions,
                                                           const std::vector<spdlog::sink_ptr>& theSinks);

      private:

        LoggerOptions                                          myOptions;
        spdlog::sink_ptr                                       mySink;
        std::mutex                                             myMutex;
        std::map<std::string, std::shared_ptr<spdlog::logger>> myLoggers;
    };

} // namespace detail
} // namespace cae
