#pragma once

#include <atomic>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include "cae_logger_detail.h"

namespace cae
{
namespace detail
{

    class Printer;

    class LoggerCore final
    {
      public:

        static LoggerCore& instance();

        void configure(LoggerOptions theOptions);
        LoggerOptions options() const;
        void update_options(LoggerOptions theOptions);
        void shutdown();

        void set_session(std::string theSessionId);
        void set_job_id(std::string theJobId);
        void set_config_path(std::string theConfigPath);

        std::string current_trace_id();

        void emit_structured(const std::string&                        theModule,
                             const std::string&                        theStage,
                             const std::string&                        theAction,
                             const std::string&                        theObjectType,
                             const std::string&                        theObjectName,
                             const std::string&                        theResult,
                             const std::string&                        theReason,
                             const std::map<std::string, MetricValue>& theMetrics,
                             const std::string&                        theEventType,
                             const std::string&                        thePhase,
                             const std::string&                        theDomain,
                             const std::string&                        theEntityType,
                             const std::string&                        theEntityName,
                             Level                                     theLevel,
                             const std::string&                        theMessage,
                             EventKind                                 theEventKind = EventKind::Point,
                             std::uint64_t                             theDurationUs = 0);
        void emit_scope_record(const std::string& theComponent,
                               const std::string& theStage,
                               const std::string& theAction,
                               Level              theLevel,
                               std::uint64_t      theDurationUs,
                               const std::string& theMessage,
                               const std::string& theTraceId,
                               const std::string& theSpanId,
                               const std::string& theParentSpanId);

      private:

        LoggerCore() = default;

        void               ensure_initialized();
        void               maybe_reload_runtime_options();
        void               emit_record(const std::string&                        theRequestedComponent,
                                       const std::string&                        theRequestedStage,
                                       const std::string&                        theRequestedAction,
                                       const std::string&                        theObjectType,
                                       const std::string&                        theObjectName,
                                       const std::string&                        theResult,
                                       const std::string&                        theReason,
                                       const std::map<std::string, MetricValue>& theMetrics,
                                       Level                                     theLevel,
                                       EventKind                                 theEventKind,
                                       std::uint64_t                             theDurationUs,
                                       std::string                               theMessage,
                                       const std::string&                        theExplicitTraceId,
                                       const std::string&                        theExplicitSpanId,
                                       const std::string&                        theExplicitParentSpanId,
                                       const std::string&                        theExplicitEventType,
                                       const std::string&                        theExplicitPhase,
                                       const std::string&                        theExplicitDomain,
                                       const std::string&                        theExplicitEntityType,
                                       const std::string&                        theExplicitEntityName);
        void               record_application_emit(const LogRecord& theRecord, const LoggerOptions& theOptionsSnapshot);
        LoggerRuntimeStats collect_runtime_stats(const std::vector<std::shared_ptr<Printer>>& thePrinters) const;
        void               emit_logger_health_snapshot();
        void               reset_runtime_stats_unlocked();
        void               create_printers_unlocked();
        void               apply_runtime_options_unlocked(LoggerOptions theOptions);
        void               close_printers_unlocked();

      private:

        mutable std::mutex                             myMutex;
        LoggerOptions                                  myOptions;
        std::string                                    mySessionId = "Single";
        std::string                                    myJobId;
        std::string                                    myConfigPath;
        Clock::time_point                              myInitTime = Clock::now();
        std::vector<std::shared_ptr<Printer>>          myPrinters;
        std::atomic<std::uint64_t>                     mySequence{0};
        std::atomic<std::uint64_t>                     myRecordsEmitted{0};
        std::atomic<std::uint64_t>                     myApplicationRecordsEmitted{0};
        std::atomic<std::uint64_t>                     myHealthEventsEmitted{0};
        std::atomic<std::uint64_t>                     myRecordsDropped{0};
        std::atomic<std::uint64_t>                     myCallChainsCaptured{0};
        std::atomic<std::uint64_t>                     myCallChainsSkipped{0};
        bool                                           myIsInitialized = false;
        optional<fs::FileTime>                         myConfigMTime;
    };

} // namespace detail
} // namespace cae
