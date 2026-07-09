#pragma once

#include <chrono>
#include <cstdint>
#include <ctime>
#include <map>
#include <string>
#include <vector>

#include "cae_filesystem.h"
#include "cae_logger_types.h"

#include <spdlog/async.h>

namespace cae
{
namespace detail
{

    using Clock = std::chrono::steady_clock;
    using SystemClock = std::chrono::system_clock;

    enum class EventKind
    {
        Point,
        Span
    };

    struct ContextFrame
    {
        std::string component;
        std::string stage;
        std::string action;
        std::string trace_id;
        std::string span_id;
    };

    struct ScopeSeed
    {
        std::string component;
        std::string stage;
        std::string action;
        std::string trace_id;
        std::string span_id;
        std::string parent_span_id;
    };

    struct LogRecord
    {
        SystemClock::time_point            timestamp;
        std::uint64_t                      timestamp_epoch_us = 0;
        std::uint64_t                      monotonic_us = 0;
        std::uint64_t                      sequence = 0;
        std::uint64_t                      logical_time = 0;
        int                                pid = 0;
        std::size_t                        tid = 0;
        std::string                        thread_name;
        std::string                        component;
        std::string                        stage;
        std::string                        action;
        Level                              level = Level::Info;
        std::string                        message;
        EventKind                          event_kind = EventKind::Point;
        std::string                        trace_id;
        std::string                        span_id;
        std::string                        parent_span_id;
        std::string                        event_id;
        std::string                        parent_event_id;
        std::string                        event_type;
        std::string                        phase;
        std::string                        domain;
        std::string                        entity_type;
        std::string                        entity_name;
        std::string                        object_type;
        std::string                        object_name;
        std::string                        result;
        std::string                        reason;
        std::map<std::string, MetricValue> metrics;
        std::vector<CallChainFrame>        call_chain;
        std::string                        call_chain_status;
        std::uint64_t                      duration_us = 0;
        std::string                        session;
        std::string                        job_id;
        std::string                        global_sequence_id;
        std::string                        node_id;
        optional<std::int32_t>             mpi_rank;
    };

    struct LoggerRuntimeStats
    {
        std::uint64_t records_emitted = 0;
        std::uint64_t application_records_emitted = 0;
        std::uint64_t health_events_emitted = 0;
        std::uint64_t records_dropped = 0;
        std::uint64_t call_chains_captured = 0;
        std::uint64_t call_chains_skipped = 0;
        std::uint64_t analysis_bytes_written = 0;
        std::uint64_t analysis_segments_created = 0;
    };

    std::string         trim(std::string theValue);
    std::string         lower_copy(std::string theValue);
    std::string         unquote(std::string theValue);
    bool                parse_bool(const std::string& theValue, bool theDefaultValue);
    std::size_t         parse_size(const std::string& theValue, std::size_t theDefaultValue);
    Level               parse_level(const std::string& theValue, Level theDefaultValue);
    ThreadModel         parse_thread_model(const std::string& theValue, ThreadModel theDefaultValue);
    ProcessModel        parse_process_model(const std::string& theValue, ProcessModel theDefaultValue);
    IOMode              parse_io_mode(const std::string& theValue, IOMode theDefaultValue);
    AsyncOverflowPolicy parse_async_overflow_policy(const std::string& theValue, AsyncOverflowPolicy theDefaultValue);
    double              parse_double(const std::string& theValue, double theDefaultValue);

    spdlog::level::level_enum     to_spdlog_level(Level theLevel);
    spdlog::async_overflow_policy to_spdlog_overflow_policy(AsyncOverflowPolicy thePolicy);
    const char*                   async_overflow_policy_to_string(AsyncOverflowPolicy thePolicy);
    const char*                   level_to_string(Level theLevel);
    std::int64_t                  metric_counter(std::uint64_t theValue);
    std::uint64_t                 clamp_duration(std::uint64_t theDurationUs);
    const char*                   event_kind_to_string(EventKind theEventKind);
    const char*                   event_type_to_string(EventType theEventType);
    const char*                   event_phase_to_string(EventPhase thePhase);
    const char*                   domain_to_string(Domain theDomain);

    int         current_pid();
    std::size_t current_tid();

    void                         set_thread_name_context(const std::string& theThreadName);
    void                         set_node_id_context(const std::string& theNodeId);
    void                         set_mpi_rank_context(optional<std::int32_t> theMpiRank);
    void                         set_logical_time_context(std::uint64_t theLogicalTime);
    optional<std::int32_t>       current_mpi_rank();
    optional<std::uint64_t>      current_logical_time();

    std::string default_thread_name();
    std::string detect_default_node_id();
    std::string derive_stage_from_component(const std::string& theComponent);

    std::string   json_escape(const std::string& theValue);
    std::string   nullable_json_string(const std::string& theValue);
    std::tm       localtime_for(SystemClock::time_point theTimePoint);
    std::string   timestamp_iso8601(SystemClock::time_point theTimePoint);
    std::uint64_t timestamp_epoch_us(SystemClock::time_point theTimePoint);

    EventType  infer_event_type(const std::string& theComponent, const std::string& theStage);
    EventPhase infer_event_phase(EventKind theEventKind, const std::string& theAction);
    Domain     infer_domain(EventType theEventType);

    fs::path      with_pid_suffix(const fs::path&    theDirectory,
                                  const std::string& theFileName,
                                  ProcessModel       theProcessModel);
    LoggerOptions         normalize_options(LoggerOptions theOptions);
    LoggerOptions         load_options_from_file(const std::string& theFilePath);

    std::string generate_trace_id();
    std::string generate_span_id();
    bool        should_sample_call_chain(double theSampleRate);

    std::string metric_value_to_json(const MetricValue& theValue);
    std::string metrics_to_json(const std::map<std::string, MetricValue>& theMetrics);

    std::vector<CallChainFrame> capture_call_chain_impl(std::size_t theMaxDepth,
                                                        std::size_t theSkip,
                                                        bool        theFilterLoggerInternalFrames);
    std::string                 call_chain_to_json(const std::vector<CallChainFrame>& theFrames);
    std::string                 call_chain_summary(const std::vector<CallChainFrame>& theFrames);
    const char*                 call_chain_status(bool theEnabled);
    std::string                 format_call_chain_frame(const CallChainFrame& theFrame);
    std::string                 format_call_chain_block(const std::vector<CallChainFrame>& theFrames);

    optional<double> current_memory_mb();

    const ContextFrame* current_context_frame();
    ScopeSeed           push_scope_context(const std::string& theRequestedComponent,
                                           const std::string& theRequestedStage,
                                           const std::string& theRequestedAction,
                                           const std::string& theExplicitTraceId);
    void                pop_scope_context(const std::string& theSpanId);
    std::string         default_scope_message(const std::string& theComponent,
                                              const std::string& theStage,
                                              const std::string& theAction);

} // namespace detail
} // namespace cae
