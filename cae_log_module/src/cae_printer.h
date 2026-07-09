#pragma once

#include <memory>
#include <string>

#include "cae_logger_detail.h"

#include <spdlog/spdlog.h>

namespace cae
{
namespace detail
{

    class Printer
    {
      public:

        virtual ~Printer() = default;

        virtual void write(const LogRecord& theRecord) = 0;
        virtual void flush();
        virtual void close();
        virtual void collect_stats(LoggerRuntimeStats& theStats) const;
        virtual void reload_options(const LoggerOptions& theOptions);

      protected:

        static void        apply_logger_options(const std::shared_ptr<spdlog::logger>& theLogger,
                                                const LoggerOptions&                   theOptions);
        static std::string format_log_message(const LogRecord& theRecord);
    };

} // namespace detail
} // namespace cae
