#include "cae_logger_core.h"

#include "cae_console_printer.h"
#include "cae_jsonl_analysis_printer.h"
#include "cae_printer.h"
#include "cae_text_file_printer.h"

#include <spdlog/async.h>
#include <spdlog/fmt/fmt.h>
#include <spdlog/spdlog.h>

namespace cae
{
namespace detail
{
    namespace
    {
        bool runtime_options_require_printer_rebuild(const LoggerOptions& theCurrent,
                                                     const LoggerOptions& theNext)
        {
            return theCurrent.thread_model != theNext.thread_model
                || theCurrent.process_model != theNext.process_model
                || theCurrent.io_mode != theNext.io_mode
                || theCurrent.enable_console != theNext.enable_console
                || theCurrent.enable_text_log != theNext.enable_text_log
                || theCurrent.enable_analysis_log != theNext.enable_analysis_log
                || theCurrent.async_queue_size != theNext.async_queue_size
                || theCurrent.async_thread_count != theNext.async_thread_count
                || theCurrent.async_overflow_policy != theNext.async_overflow_policy
                || theCurrent.log_dir != theNext.log_dir
                || theCurrent.analysis_log_name != theNext.analysis_log_name;
        }
    }

    //=======================================================================
    // function : LoggerCore::instance
    // purpose  :
    //=======================================================================
    LoggerCore& LoggerCore::instance()
    {
        static LoggerCore aCore;
        return aCore;
    }

    //=======================================================================
    // function : LoggerCore::configure
    // purpose  :
    //=======================================================================
    void LoggerCore::configure(LoggerOptions theOptions)
    {
        theOptions = normalize_options(std::move(theOptions));

        std::lock_guard<std::mutex> aLock(myMutex);
        close_printers_unlocked();

        myOptions = std::move(theOptions);
        mySessionId = "Single";
        myJobId = myOptions.job_id;
        myConfigPath.clear();
        myInitTime = Clock::now();
        mySequence.store(0, std::memory_order_relaxed);
        myConfigMTime.reset();
        reset_runtime_stats_unlocked();
        myIsInitialized = true;

        create_printers_unlocked();
    }

    //=======================================================================
    // function : LoggerCore::options
    // purpose  :
    //=======================================================================
    LoggerOptions LoggerCore::options() const
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        if (!myIsInitialized)
        {
            return normalize_options(LoggerOptions{});
        }

        return myOptions;
    }

    //=======================================================================
    // function : LoggerCore::update_options
    // purpose  :
    //=======================================================================
    void LoggerCore::update_options(LoggerOptions theOptions)
    {
        theOptions = normalize_options(std::move(theOptions));

        std::lock_guard<std::mutex> aLock(myMutex);
        if (!myIsInitialized)
        {
            myOptions = std::move(theOptions);
            myJobId = myOptions.job_id;
            myInitTime = Clock::now();
            reset_runtime_stats_unlocked();
            myIsInitialized = true;
            create_printers_unlocked();
            return;
        }

        apply_runtime_options_unlocked(std::move(theOptions));
    }

    //=======================================================================
    // function : LoggerCore::shutdown
    // purpose  :
    //=======================================================================
    void LoggerCore::shutdown()
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        close_printers_unlocked();
        myIsInitialized = false;
        spdlog::shutdown();
    }

    //=======================================================================
    // function : LoggerCore::set_session
    // purpose  :
    //=======================================================================
    void LoggerCore::set_session(std::string theSessionId)
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        mySessionId = theSessionId.empty() ? "Single" : std::move(theSessionId);
    }

    //=======================================================================
    // function : LoggerCore::set_job_id
    // purpose  :
    //=======================================================================
    void LoggerCore::set_job_id(std::string theJobId)
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        myJobId = std::move(theJobId);
    }

    //=======================================================================
    // function : LoggerCore::set_config_path
    // purpose  :
    //=======================================================================
    void LoggerCore::set_config_path(std::string theConfigPath)
    {
        optional<fs::FileTime> aConfigMTime;
        if (!theConfigPath.empty())
        {
            std::error_code       anError;
            const fs::FileTime    aCurrentWriteTime = fs::last_write_time(fs::path(theConfigPath), anError);
            if (!anError)
            {
                aConfigMTime = aCurrentWriteTime;
            }
        }

        std::lock_guard<std::mutex> aLock(myMutex);
        myConfigPath = std::move(theConfigPath);
        myConfigMTime = aConfigMTime;
    }

    //=======================================================================
    // function : LoggerCore::current_trace_id
    // purpose  :
    //=======================================================================
    std::string LoggerCore::current_trace_id()
    {
        const ContextFrame* aCurrentFrame = current_context_frame();
        return aCurrentFrame != nullptr ? aCurrentFrame->trace_id : "";
    }

    //=======================================================================
    // function : LoggerCore::emit_structured
    // purpose  :
    //=======================================================================
    void LoggerCore::emit_structured(const std::string&                        theModule,
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
                                     EventKind                                 theEventKind,
                                     std::uint64_t                             theDurationUs)
    {
        emit_record(theModule,
                    theStage,
                    theAction,
                    theObjectType,
                    theObjectName,
                    theResult,
                    theReason,
                    theMetrics,
                    theLevel,
                    theEventKind,
                    theDurationUs,
                    theMessage,
                    "",
                    "",
                    "",
                    theEventType,
                    thePhase,
                    theDomain,
                    theEntityType,
                    theEntityName);
    }

    //=======================================================================
    // function : LoggerCore::emit_scope_record
    // purpose  :
    //=======================================================================
    void LoggerCore::emit_scope_record(const std::string& theComponent,
                                       const std::string& theStage,
                                       const std::string& theAction,
                                       Level              theLevel,
                                       std::uint64_t      theDurationUs,
                                       const std::string& theMessage,
                                       const std::string& theTraceId,
                                       const std::string& theSpanId,
                                       const std::string& theParentSpanId)
    {
        emit_record(theComponent,
                    theStage,
                    theAction,
                    "",
                    "",
                    "completed",
                    "",
                    {},
                    theLevel,
                    EventKind::Span,
                    theDurationUs,
                    theMessage,
                    theTraceId,
                    theSpanId,
                    theParentSpanId,
                    "",
                    "",
                    "",
                    "",
                    "");
    }

    //=======================================================================
    // function : LoggerCore::ensure_initialized
    // purpose  :
    //=======================================================================
    void LoggerCore::ensure_initialized()
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        if (myIsInitialized)
        {
            return;
        }

        myOptions = normalize_options(LoggerOptions{});
        myInitTime = Clock::now();
        reset_runtime_stats_unlocked();
        create_printers_unlocked();
        myIsInitialized = true;
    }

    //=======================================================================
    // function : LoggerCore::maybe_reload_runtime_options
    // purpose  :
    //=======================================================================
    void LoggerCore::maybe_reload_runtime_options()
    {
        std::string aConfigPath;
        {
            std::lock_guard<std::mutex> aLock(myMutex);
            if (myConfigPath.empty())
            {
                return;
            }
            aConfigPath = myConfigPath;
        }

        if (aConfigPath.empty())
        {
            return;
        }

        std::error_code anError;
        const fs::FileTime aCurrentWriteTime = fs::last_write_time(fs::path(aConfigPath), anError);
        if (anError)
        {
            return;
        }

        bool toReload = false;
        {
            std::lock_guard<std::mutex> aLock(myMutex);
            if (aConfigPath != myConfigPath)
            {
                return;
            }
            if (!myConfigMTime.has_value() || aCurrentWriteTime != *myConfigMTime)
            {
                myConfigMTime = aCurrentWriteTime;
                toReload = true;
            }
        }
        if (!toReload)
        {
            return;
        }

        const LoggerOptions         aReloaded = normalize_options(load_options_from_file(aConfigPath));
        std::lock_guard<std::mutex> aLock(myMutex);
        if (aConfigPath != myConfigPath)
        {
            return;
        }
        apply_runtime_options_unlocked(aReloaded);
        myConfigMTime = aCurrentWriteTime;
    }

    //=======================================================================
    // function : LoggerCore::emit_record
    // purpose  :
    //=======================================================================
    void LoggerCore::emit_record(const std::string&                        theRequestedComponent,
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
                                 const std::string&                        theExplicitEntityName)
    {
        ensure_initialized();
        maybe_reload_runtime_options();

        const auto          aSteadyNow = Clock::now();
        const ContextFrame* aCurrentFrame = current_context_frame();

        LogRecord aRecord;
        aRecord.timestamp = SystemClock::now();
        aRecord.timestamp_epoch_us = timestamp_epoch_us(aRecord.timestamp);
        aRecord.sequence = mySequence.fetch_add(1, std::memory_order_relaxed) + 1;
        const optional<std::uint64_t> aLogicalTime = current_logical_time();
        aRecord.logical_time = aLogicalTime.has_value() ? *aLogicalTime : aRecord.sequence;
        aRecord.pid = current_pid();
        aRecord.tid = current_tid();
        aRecord.thread_name = default_thread_name();
        aRecord.component = theRequestedComponent.empty()
                              ? (aCurrentFrame != nullptr ? aCurrentFrame->component : "default")
                              : theRequestedComponent;
        aRecord.stage = theRequestedStage.empty()
                          ? (aCurrentFrame != nullptr ? aCurrentFrame->stage
                                                      : derive_stage_from_component(aRecord.component))
                          : theRequestedStage;
        aRecord.action = theRequestedAction.empty() ? (aCurrentFrame != nullptr ? aCurrentFrame->action : "message")
                                                    : theRequestedAction;
        aRecord.level = theLevel;
        aRecord.message = theMessage.empty() ? "structured event" : std::move(theMessage);
        aRecord.event_kind = theEventKind;
        aRecord.trace_id = !theExplicitTraceId.empty()
                             ? theExplicitTraceId
                             : (aCurrentFrame != nullptr ? aCurrentFrame->trace_id : generate_trace_id());
        aRecord.span_id = !theExplicitSpanId.empty() ? theExplicitSpanId : generate_span_id();
        aRecord.parent_span_id = !theExplicitParentSpanId.empty()
                                   ? theExplicitParentSpanId
                                   : (aCurrentFrame != nullptr ? aCurrentFrame->span_id : "");
        aRecord.object_type = theObjectType;
        aRecord.object_name = theObjectName;
        aRecord.result = theResult;
        aRecord.reason = theReason;
        aRecord.metrics = theMetrics;
        aRecord.duration_us = theEventKind == EventKind::Span ? clamp_duration(theDurationUs) : 0;
        aRecord.node_id = detect_default_node_id();
        aRecord.mpi_rank = current_mpi_rank();
        aRecord.event_id = aRecord.span_id;
        aRecord.parent_event_id = aRecord.parent_span_id;

        const EventType anInferredEventType = infer_event_type(aRecord.component, aRecord.stage);
        aRecord.event_type = theExplicitEventType.empty() ? event_type_to_string(anInferredEventType)
                                                          : theExplicitEventType;
        aRecord.phase = theExplicitPhase.empty()
                          ? event_phase_to_string(infer_event_phase(aRecord.event_kind, aRecord.action))
                          : theExplicitPhase;
        aRecord.domain = theExplicitDomain.empty() ? domain_to_string(infer_domain(anInferredEventType))
                                                   : theExplicitDomain;
        aRecord.entity_type = theExplicitEntityType.empty()
                                ? (!aRecord.object_type.empty() ? aRecord.object_type : aRecord.stage)
                                : theExplicitEntityType;
        aRecord.entity_name = theExplicitEntityName.empty()
                                ? (!aRecord.object_name.empty() ? aRecord.object_name : aRecord.action)
                                : theExplicitEntityName;

        if (aRecord.event_kind == EventKind::Span)
        {
            const optional<double> aMemoryMb = current_memory_mb();
            if (aMemoryMb.has_value())
            {
                aRecord.metrics["memory_mb"] = *aMemoryMb;
            }
        }

        std::vector<std::shared_ptr<Printer>> aPrinters;
        LoggerOptions                         anOptionsSnapshot;
        {
            std::lock_guard<std::mutex> aLock(myMutex);
            if (theLevel < myOptions.min_level)
            {
                return;
            }
            if (myOptions.enable_lossy_drop_policy && theLevel < myOptions.lossy_drop_below_level)
            {
                myRecordsDropped.fetch_add(1, std::memory_order_relaxed);
                return;
            }

            anOptionsSnapshot = myOptions;
            aRecord.session = mySessionId.empty() ? "Single" : mySessionId;
            aRecord.job_id = myJobId.empty() ? aRecord.session : myJobId;
            aRecord.monotonic_us = static_cast<std::uint64_t>(
                std::chrono::duration_cast<std::chrono::microseconds>(aSteadyNow - myInitTime).count());
            aRecord.global_sequence_id = fmt::format("{}:{}:{}:{}",
                                                     aRecord.job_id,
                                                     aRecord.node_id,
                                                     aRecord.mpi_rank.has_value() ? std::to_string(*aRecord.mpi_rank)
                                                                                  : "na",
                                                     aRecord.sequence);
            aPrinters.reserve(myPrinters.size());
            for (const auto& aPrinter : myPrinters)
            {
                aPrinters.push_back(aPrinter);
            }
        }

        const bool toCaptureCallChain = anOptionsSnapshot.enable_call_chain_analysis
                                     && theLevel >= anOptionsSnapshot.call_chain_min_level
                                     && should_sample_call_chain(anOptionsSnapshot.call_chain_sample_rate);
        aRecord.call_chain_status = call_chain_status(toCaptureCallChain);
        if (toCaptureCallChain)
        {
            aRecord.call_chain = capture_call_chain_impl(anOptionsSnapshot.call_chain_max_depth,
                                                         anOptionsSnapshot.call_chain_skip,
                                                         true);
        }

        for (const auto& aPrinter : aPrinters)
        {
            aPrinter->write(aRecord);
        }

        record_application_emit(aRecord, anOptionsSnapshot);
    }

    //=======================================================================
    // function : LoggerCore::record_application_emit
    // purpose  :
    //=======================================================================
    void LoggerCore::record_application_emit(const LogRecord& theRecord, const LoggerOptions& theOptionsSnapshot)
    {
        myRecordsEmitted.fetch_add(1, std::memory_order_relaxed);
        const auto anApplicationRecords = myApplicationRecordsEmitted.fetch_add(1, std::memory_order_relaxed) + 1;
        if (theRecord.call_chain_status == "captured")
        {
            myCallChainsCaptured.fetch_add(1, std::memory_order_relaxed);
        }
        else
        {
            myCallChainsSkipped.fetch_add(1, std::memory_order_relaxed);
        }

        const auto anInterval = theOptionsSnapshot.logger_health_interval_events;
        if (anInterval > 0 && anApplicationRecords % anInterval == 0)
        {
            emit_logger_health_snapshot();
        }
    }

    //=======================================================================
    // function : LoggerCore::collect_runtime_stats
    // purpose  :
    //=======================================================================
    LoggerRuntimeStats LoggerCore::collect_runtime_stats(const std::vector<std::shared_ptr<Printer>>& thePrinters) const
    {
        LoggerRuntimeStats aStats;
        aStats.records_emitted = myRecordsEmitted.load(std::memory_order_relaxed);
        aStats.application_records_emitted = myApplicationRecordsEmitted.load(std::memory_order_relaxed);
        aStats.health_events_emitted = myHealthEventsEmitted.load(std::memory_order_relaxed);
        aStats.records_dropped = myRecordsDropped.load(std::memory_order_relaxed);
        aStats.call_chains_captured = myCallChainsCaptured.load(std::memory_order_relaxed);
        aStats.call_chains_skipped = myCallChainsSkipped.load(std::memory_order_relaxed);
        for (const auto& aPrinter : thePrinters)
        {
            aPrinter->collect_stats(aStats);
        }

        return aStats;
    }

    //=======================================================================
    // function : LoggerCore::emit_logger_health_snapshot
    // purpose  :
    //=======================================================================
    void LoggerCore::emit_logger_health_snapshot()
    {
        const auto                            aSteadyNow = Clock::now();
        std::vector<std::shared_ptr<Printer>> aPrinters;
        LoggerOptions                         anOptionsSnapshot;
        std::string                           aSession;
        std::string                           aJobId;
        Clock::time_point                     anInitTime;
        {
            std::lock_guard<std::mutex> aLock(myMutex);
            if (!myIsInitialized || Level::Info < myOptions.min_level)
            {
                return;
            }

            anOptionsSnapshot = myOptions;
            aSession = mySessionId.empty() ? "Single" : mySessionId;
            aJobId = myJobId.empty() ? aSession : myJobId;
            anInitTime = myInitTime;
            aPrinters.reserve(myPrinters.size());
            for (const auto& aPrinter : myPrinters)
            {
                aPrinters.push_back(aPrinter);
            }
        }

        const auto         aTotalRecords = myRecordsEmitted.fetch_add(1, std::memory_order_relaxed) + 1;
        const auto         aHealthEvents = myHealthEventsEmitted.fetch_add(1, std::memory_order_relaxed) + 1;
        LoggerRuntimeStats aStats = collect_runtime_stats(aPrinters);
        aStats.records_emitted = aTotalRecords;
        aStats.health_events_emitted = aHealthEvents;

        LogRecord aRecord;
        aRecord.timestamp = SystemClock::now();
        aRecord.timestamp_epoch_us = timestamp_epoch_us(aRecord.timestamp);
        aRecord.monotonic_us = static_cast<std::uint64_t>(
            std::chrono::duration_cast<std::chrono::microseconds>(aSteadyNow - anInitTime).count());
        aRecord.sequence = mySequence.fetch_add(1, std::memory_order_relaxed) + 1;
        const optional<std::uint64_t> aLogicalTime = current_logical_time();
        aRecord.logical_time = aLogicalTime.has_value() ? *aLogicalTime : aRecord.sequence;
        aRecord.pid = current_pid();
        aRecord.tid = current_tid();
        aRecord.thread_name = default_thread_name();
        aRecord.component = "Logger";
        aRecord.stage = "Runtime";
        aRecord.action = "health_snapshot";
        aRecord.level = Level::Info;
        aRecord.message = "Logger runtime health snapshot.";
        aRecord.event_kind = EventKind::Point;
        aRecord.trace_id = generate_trace_id();
        aRecord.span_id = generate_span_id();
        aRecord.event_id = aRecord.span_id;
        aRecord.parent_span_id.clear();
        aRecord.parent_event_id.clear();
        aRecord.event_type = event_type_to_string(EventType::System);
        aRecord.phase = event_phase_to_string(EventPhase::Progress);
        aRecord.domain = domain_to_string(Domain::System);
        aRecord.entity_type = "logger";
        aRecord.entity_name = "runtime_health";
        aRecord.result = "ok";
        aRecord.duration_us = 0;
        aRecord.session = aSession;
        aRecord.job_id = aJobId;
        aRecord.node_id = detect_default_node_id();
        aRecord.mpi_rank = current_mpi_rank();
        aRecord.global_sequence_id = fmt::format("{}:{}:{}:{}",
                                                 aRecord.job_id,
                                                 aRecord.node_id,
                                                 aRecord.mpi_rank.has_value() ? std::to_string(*aRecord.mpi_rank)
                                                                              : "na",
                                                 aRecord.sequence);
        aRecord.call_chain_status = "disabled";
        aRecord.metrics = {{"records_emitted", metric_counter(aStats.records_emitted)},
                           {"application_records_emitted", metric_counter(aStats.application_records_emitted)},
                           {"health_events_emitted", metric_counter(aStats.health_events_emitted)},
                           {"records_dropped", metric_counter(aStats.records_dropped)},
                           {"call_chains_captured", metric_counter(aStats.call_chains_captured)},
                           {"call_chains_skipped", metric_counter(aStats.call_chains_skipped)},
                           {"analysis_bytes_written", metric_counter(aStats.analysis_bytes_written)},
                           {"analysis_segments_created", metric_counter(aStats.analysis_segments_created)},
                           {"async_queue_size", metric_counter(anOptionsSnapshot.async_queue_size)},
                           {"async_thread_count", metric_counter(anOptionsSnapshot.async_thread_count)},
                           {"async_overflow_policy",
                            std::string(async_overflow_policy_to_string(anOptionsSnapshot.async_overflow_policy))},
                           {"enable_lossy_drop_policy", anOptionsSnapshot.enable_lossy_drop_policy},
                           {"lossy_drop_below_level",
                            std::string(level_to_string(anOptionsSnapshot.lossy_drop_below_level))}};

        for (const auto& aPrinter : aPrinters)
        {
            aPrinter->write(aRecord);
        }
    }

    //=======================================================================
    // function : LoggerCore::reset_runtime_stats_unlocked
    // purpose  :
    //=======================================================================
    void LoggerCore::reset_runtime_stats_unlocked()
    {
        myRecordsEmitted.store(0, std::memory_order_relaxed);
        myApplicationRecordsEmitted.store(0, std::memory_order_relaxed);
        myHealthEventsEmitted.store(0, std::memory_order_relaxed);
        myRecordsDropped.store(0, std::memory_order_relaxed);
        myCallChainsCaptured.store(0, std::memory_order_relaxed);
        myCallChainsSkipped.store(0, std::memory_order_relaxed);
    }

    //=======================================================================
    // function : LoggerCore::create_printers_unlocked
    // purpose  :
    //=======================================================================
    void LoggerCore::create_printers_unlocked()
    {
        fs::create_directories(myOptions.log_dir);
        if (myOptions.io_mode == IOMode::Async)
        {
            spdlog::init_thread_pool(myOptions.async_queue_size, myOptions.async_thread_count);
        }

        if (myOptions.enable_console)
        {
            myPrinters.push_back(std::make_shared<ConsolePrinter>(myOptions));
        }
        if (myOptions.enable_text_log)
        {
            myPrinters.push_back(std::make_shared<TextFilePrinter>(myOptions));
        }
        if (myOptions.enable_analysis_log)
        {
            myPrinters.push_back(std::make_shared<JsonlAnalysisPrinter>(myOptions));
        }
    }

    //=======================================================================
    // function : LoggerCore::apply_runtime_options_unlocked
    // purpose  :
    //=======================================================================
    void LoggerCore::apply_runtime_options_unlocked(LoggerOptions theOptions)
    {
        const bool toRebuildPrinters = runtime_options_require_printer_rebuild(myOptions, theOptions);

        if (toRebuildPrinters)
        {
            close_printers_unlocked();
        }

        myOptions = std::move(theOptions);
        if (!myOptions.job_id.empty())
        {
            myJobId = myOptions.job_id;
        }

        if (toRebuildPrinters)
        {
            create_printers_unlocked();
            return;
        }

        for (const auto& aPrinter : myPrinters)
        {
            aPrinter->reload_options(myOptions);
        }
    }

    //=======================================================================
    // function : LoggerCore::close_printers_unlocked
    // purpose  :
    //=======================================================================
    void LoggerCore::close_printers_unlocked()
    {
        for (const auto& aPrinter : myPrinters)
        {
            aPrinter->flush();
            aPrinter->close();
        }

        myPrinters.clear();
    }

} // namespace detail
} // namespace cae
