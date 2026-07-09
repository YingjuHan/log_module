#pragma once

#include <map>
#include <memory>
#include <mutex>
#include <string>

#include "cae_printer.h"

#include <spdlog/spdlog.h>

namespace cae
{
namespace detail
{

    class TextFilePrinter final : public Printer
    {
      public:

        explicit TextFilePrinter(LoggerOptions theOptions);

        void write(const LogRecord& theRecord) override;
        void flush() override;
        void close() override;
        void reload_options(const LoggerOptions& theOptions) override;

      private:

        std::shared_ptr<spdlog::logger> get_or_create(const std::string& theModule);
        fs::path                        module_log_path(const std::string& theModule) const;

      private:

        LoggerOptions                                          myOptions;
        std::mutex                                             myMutex;
        std::map<std::string, std::shared_ptr<spdlog::logger>> myLoggers;
    };

} // namespace detail
} // namespace cae
