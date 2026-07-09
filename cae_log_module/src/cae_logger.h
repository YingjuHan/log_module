#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "cae_compat.h"
#include "cae_event_schema.h"
#include "cae_log_builder.h"
#include "cae_logger_export.h"
#include "cae_logger_types.h"
#include "cae_scoped_timer.h"
#include "cae_task_scope.h"

namespace cae
{

/**
 * \brief Initializes the global CAE logger from an INI-style configuration file.
 *
 * When the path is empty, the logger uses built-in defaults and the runtime
 * configuration discovery implemented by the library. Call this before emitting
 * application logs when deterministic output paths or levels are required.
 *
 * \param theConfigPath Optional path to `cae_logger_config.ini`.
 */
CAE_LOGGER_EXPORT void init(const std::string& theConfigPath = "");

/**
 * \brief Initializes the global CAE logger from explicit runtime options.
 *
 * This overload is useful for tests, embedded integrations, and applications
 * that already own configuration parsing. The options are copied by the logger.
 *
 * \param theOptions Complete runtime and output configuration.
 */
CAE_LOGGER_EXPORT void init(const LoggerOptions& theOptions);

//! Sets the logical session or case identifier written to subsequent records.
CAE_LOGGER_EXPORT void set_session(const std::string& theSessionId);

//! Sets a readable name for the current thread in emitted log records.
CAE_LOGGER_EXPORT void set_thread_name(const std::string& theThreadName);

//! Sets the distributed node identifier written to subsequent records.
CAE_LOGGER_EXPORT void set_node_id(const std::string& theNodeId);

//! Sets or clears the MPI rank written to subsequent records.
CAE_LOGGER_EXPORT void set_mpi_rank(optional<std::int32_t> theMpiRank);

//! Sets the MPI rank written to subsequent records.
CAE_LOGGER_EXPORT void set_mpi_rank(std::int32_t theMpiRank);

//! Clears the MPI rank for the current logging context.
CAE_LOGGER_EXPORT void clear_mpi_rank();

//! Sets the job or batch identifier written to subsequent records.
CAE_LOGGER_EXPORT void set_job_id(const std::string& theJobId);

//! Sets the caller-defined logical clock value written to subsequent records.
CAE_LOGGER_EXPORT void set_logical_time(std::uint64_t theLogicalTime);

//! Returns the logger's current thread name for the calling thread.
CAE_LOGGER_EXPORT std::string get_thread_name();

//! Returns the current trace identifier, creating one if needed.
CAE_LOGGER_EXPORT std::string get_trace_id();

/**
 * \brief Captures a native C++ call chain for diagnostic records.
 *
 * \param theMaxDepth Maximum number of frames to return.
 * \param theSkip Number of innermost frames to omit from the result.
 * \return Captured call-chain frames. The vector may be empty when capture is
 * disabled or unavailable on the current platform.
 */
CAE_LOGGER_EXPORT std::vector<CallChainFrame> capture_call_chain(std::size_t theMaxDepth = 16, std::size_t theSkip = 0);

//! Formats captured call-chain frames into a compact text representation.
CAE_LOGGER_EXPORT std::string format_call_chain(const std::vector<CallChainFrame>& theFrames);

//! Creates a fluent structured-event builder at the requested severity level.
CAE_LOGGER_EXPORT LogBuilder make_log_builder(Level theLevel);

//! Flushes and releases logger resources. Call during normal application exit.
CAE_LOGGER_EXPORT void shutdown();

} // namespace cae

/**
 * \defgroup cae_logger_macros CAE logger convenience macros
 * \brief Public macro layer for structured events, text events, and RAII spans.
 *
 * The macros create `cae::LogBuilder`, `cae::ScopedTimer`, or
 * `cae::TaskScope` objects. Builder-returning macros do not emit records until
 * the caller finishes the chain with `submit()`.
 * \{
 */

//! Creates a `cae::LogBuilder` for a structured event at the named level.
#define CAE_LOG(level) cae::make_log_builder(cae::Level::level)

//! Creates a TRACE text-event builder for the specified module.
#define CAE_LOG_TRACE(theModule)    cae::make_log_builder(cae::Level::Trace).module(theModule)
//! Creates a DEBUG text-event builder for the specified module.
#define CAE_LOG_DEBUG(theModule)    cae::make_log_builder(cae::Level::Debug).module(theModule)
//! Creates an INFO text-event builder for the specified module.
#define CAE_LOG_INFO(theModule)     cae::make_log_builder(cae::Level::Info).module(theModule)
//! Creates a WARN text-event builder for the specified module.
#define CAE_LOG_WARN(theModule)     cae::make_log_builder(cae::Level::Warn).module(theModule)
//! Creates an ERROR text-event builder for the specified module.
#define CAE_LOG_ERROR(theModule)    cae::make_log_builder(cae::Level::Error).module(theModule)
//! Creates a CRITICAL text-event builder for the specified module.
#define CAE_LOG_CRITICAL(theModule) cae::make_log_builder(cae::Level::Critical).module(theModule)

//! Creates a TRACE builder with an explicit duration in microseconds.
#define CAE_LOG_TRACE_DUR(theModule, theDurationUs) \
    cae::make_log_builder(cae::Level::Trace).module(theModule).duration_us(static_cast<std::uint64_t>(theDurationUs))
//! Creates a DEBUG builder with an explicit duration in microseconds.
#define CAE_LOG_DEBUG_DUR(theModule, theDurationUs) \
    cae::make_log_builder(cae::Level::Debug).module(theModule).duration_us(static_cast<std::uint64_t>(theDurationUs))
//! Creates an INFO builder with an explicit duration in microseconds.
#define CAE_LOG_INFO_DUR(theModule, theDurationUs) \
    cae::make_log_builder(cae::Level::Info).module(theModule).duration_us(static_cast<std::uint64_t>(theDurationUs))
//! Creates a WARN builder with an explicit duration in microseconds.
#define CAE_LOG_WARN_DUR(theModule, theDurationUs) \
    cae::make_log_builder(cae::Level::Warn).module(theModule).duration_us(static_cast<std::uint64_t>(theDurationUs))
//! Creates an ERROR builder with an explicit duration in microseconds.
#define CAE_LOG_ERROR_DUR(theModule, theDurationUs) \
    cae::make_log_builder(cae::Level::Error).module(theModule).duration_us(static_cast<std::uint64_t>(theDurationUs))
//! Creates a CRITICAL builder with an explicit duration in microseconds.
#define CAE_LOG_CRITICAL_DUR(theModule, theDurationUs) \
    cae::make_log_builder(cae::Level::Critical).module(theModule).duration_us(static_cast<std::uint64_t>(theDurationUs))

#define CAE_LOG_DETAIL_CONCAT_INNER(lhs, rhs) lhs##rhs
#define CAE_LOG_DETAIL_CONCAT(lhs, rhs)       CAE_LOG_DETAIL_CONCAT_INNER(lhs, rhs)

//! Creates a scoped timer that emits a span when the current C++ scope exits.
#define CAE_LOG_SCOPE(level, module, ...)                  \
    cae::ScopedTimer CAE_LOG_DETAIL_CONCAT(cae_log_scope_, \
                                           __LINE__)(module, cae::Level::level, fmt::format(__VA_ARGS__))
//! Creates a workflow task scope that emits a structured span on destruction.
#define CAE_SCOPE_TASK(level, module, stage, ...) \
    cae::TaskScope CAE_LOG_DETAIL_CONCAT(cae_task_scope_, __LINE__)(module, stage, cae::Level::level, ##__VA_ARGS__)

//! TRACE shortcut for `CAE_LOG_SCOPE`.
#define CAE_LOG_SCOPE_TRACE(module, ...)    CAE_LOG_SCOPE(Trace, module, __VA_ARGS__)
//! DEBUG shortcut for `CAE_LOG_SCOPE`.
#define CAE_LOG_SCOPE_DEBUG(module, ...)    CAE_LOG_SCOPE(Debug, module, __VA_ARGS__)
//! INFO shortcut for `CAE_LOG_SCOPE`.
#define CAE_LOG_SCOPE_INFO(module, ...)     CAE_LOG_SCOPE(Info, module, __VA_ARGS__)
//! WARN shortcut for `CAE_LOG_SCOPE`.
#define CAE_LOG_SCOPE_WARN(module, ...)     CAE_LOG_SCOPE(Warn, module, __VA_ARGS__)
//! ERROR shortcut for `CAE_LOG_SCOPE`.
#define CAE_LOG_SCOPE_ERROR(module, ...)    CAE_LOG_SCOPE(Error, module, __VA_ARGS__)
//! CRITICAL shortcut for `CAE_LOG_SCOPE`.
#define CAE_LOG_SCOPE_CRITICAL(module, ...) CAE_LOG_SCOPE(Critical, module, __VA_ARGS__)

//! \}
