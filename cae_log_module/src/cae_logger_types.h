#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

#include "cae_compat.h"
#include "cae_event_schema.h"
#include "cae_logger_export.h"

namespace cae
{

//! Severity level used for filtering, routing, and human-facing impact.
enum class Level
{
    //! Very detailed diagnostics, normally disabled in production.
    Trace = 0,
    //! Developer diagnostics useful while investigating behavior.
    Debug = 1,
    //! Normal business progress and summaries.
    Info = 2,
    //! Recoverable conditions that deserve operator attention.
    Warn = 3,
    //! Failed actions whose result is unavailable or incomplete.
    Error = 4,
    //! Fatal or globally unsafe conditions.
    Critical = 5
};

//! Declares whether the process emits logs from one or many threads.
enum class ThreadModel
{
    //! Logging is produced from one thread.
    SingleThread,
    //! Logging may be produced concurrently from multiple threads.
    MultiThread
};

//! Declares whether one or many processes may participate in a run.
enum class ProcessModel
{
    //! One process writes the configured log files.
    SingleProcess,
    //! Multiple processes or ranks participate in the same workflow.
    MultiProcess
};

//! Selects synchronous or asynchronous log I/O.
enum class IOMode
{
    //! Emit records on the caller path.
    Sync,
    //! Queue records and let background workers perform file I/O.
    Async
};

//! Runtime type tag for a metric value stored in structured JSONL output.
enum class MetricValueType
{
    //! Signed integer metric.
    Integer,
    //! Floating-point metric.
    Double,
    //! Boolean metric.
    Boolean,
    //! String metric.
    String
};

//! Type-erased value container for a single structured metric.
class MetricValue
{
  public:

    //! Creates an integer metric value initialized to zero.
    MetricValue() : myType(MetricValueType::Integer), myInteger(0), myDouble(0.0), myBoolean(false)
    {
    }

    //! Creates a signed integer metric value.
    MetricValue(std::int64_t theValue)
    : myType(MetricValueType::Integer), myInteger(theValue), myDouble(0.0), myBoolean(false)
    {
    }

    //! Creates a floating-point metric value.
    MetricValue(double theValue)
    : myType(MetricValueType::Double), myInteger(0), myDouble(theValue), myBoolean(false)
    {
    }

    //! Creates a boolean metric value.
    MetricValue(bool theValue)
    : myType(MetricValueType::Boolean), myInteger(0), myDouble(0.0), myBoolean(theValue)
    {
    }

    //! Creates a string metric value.
    MetricValue(const std::string& theValue)
    : myType(MetricValueType::String), myInteger(0), myDouble(0.0), myBoolean(false), myString(theValue)
    {
    }

    //! Creates a string metric value; null input is stored as an empty string.
    MetricValue(const char* theValue)
    : myType(MetricValueType::String),
      myInteger(0),
      myDouble(0.0),
      myBoolean(false),
      myString(theValue != nullptr ? theValue : "")
    {
    }

    //! Returns the active metric value type.
    MetricValueType type() const
    {
        return myType;
    }

    //! Returns the integer storage slot.
    std::int64_t integer_value() const
    {
        return myInteger;
    }

    //! Returns the double storage slot.
    double double_value() const
    {
        return myDouble;
    }

    //! Returns the boolean storage slot.
    bool bool_value() const
    {
        return myBoolean;
    }

    //! Returns the string storage slot.
    const std::string& string_value() const
    {
        return myString;
    }

  private:

    MetricValueType myType;
    std::int64_t    myInteger;
    double          myDouble;
    bool            myBoolean;
    std::string     myString;
};

//! Describes one captured call-chain frame for analysis logging.
struct CAE_LOGGER_EXPORT CallChainFrame
{
    //! Zero-based frame index after skip handling.
    std::size_t index = 0;
    //! Best-effort function or symbol name.
    std::string function;
    //! Best-effort source file path, when available.
    std::string source_file;
    //! Best-effort source line number, or zero when unknown.
    std::size_t source_line = 0;
    //! Native instruction address as text.
    std::string address;
};

//! Aggregates runtime and output configuration for the CAE logger.
struct CAE_LOGGER_EXPORT LoggerOptions
{
    //! Threading model assumed by the logger runtime.
    ThreadModel  thread_model = ThreadModel::MultiThread;
    //! Process model used for file naming and runtime context.
    ProcessModel process_model = ProcessModel::SingleProcess;
    //! Synchronous or asynchronous output mode.
    IOMode       io_mode = IOMode::Async;

    //! Enables human-readable console output.
    bool enable_console = true;
    //! Enables human-readable text log files.
    bool enable_text_log = true;
    //! Enables structured JSONL analysis log files.
    bool enable_analysis_log = true;
    //! Truncates existing log files during initialization when true.
    bool truncate_file = false;

    //! Maximum async queue size before overflow handling applies.
    std::size_t         async_queue_size = 8192;
    //! Number of async worker threads.
    std::size_t         async_thread_count = 1;
    //! Queue overflow behavior used by the async backend.
    AsyncOverflowPolicy async_overflow_policy = AsyncOverflowPolicy::Block;
    //! Enables level-based dropping before queue insertion.
    bool                enable_lossy_drop_policy = false;
    //! Drops records below this level when lossy dropping is enabled.
    Level               lossy_drop_below_level = Level::Trace;

    //! Minimum severity level emitted by the logger.
    Level min_level = Level::Trace;
    //! Severity level that triggers flush behavior.
    Level flush_level = Level::Error;
    //! Flushes file outputs after every accepted record for crash/debug visibility.
    bool flush_each_record = true;

    //! Directory where log files are written.
    std::string log_dir = "logs";
    //! File name for structured JSONL analysis output.
    std::string analysis_log_name = "cae_events.jsonl";
    //! Maximum JSONL file size before rotation logic applies.
    std::size_t analysis_log_max_bytes = 128 * 1024 * 1024;
    //! Number of rotated analysis log files to retain; zero keeps all.
    std::size_t analysis_log_retention_files = 0;
    //! Emits logger health snapshots every N application records.
    std::size_t logger_health_interval_events = 1000;
    //! spdlog-compatible text log pattern.
    std::string global_pattern = "[%Y-%m-%d %H:%M:%S.%e] [%t] [%n] [%^%l%$] %v";
    //! Optional job or batch identifier written to records.
    std::string job_id;

    //! Captures native C++ call chains into text logs and structured JSONL rows.
    bool        enable_call_chain_analysis = true;
    //! Minimum severity that triggers automatic call-chain capture.
    Level       call_chain_min_level = Level::Error;
    //! Maximum number of captured frames.
    std::size_t call_chain_max_depth = 16;
    //! Number of innermost frames to skip.
    std::size_t call_chain_skip = 0;
    //! Sampling rate from 0.0 to 1.0 for automatic call-chain capture.
    double      call_chain_sample_rate = 1.0;
};

} // namespace cae
