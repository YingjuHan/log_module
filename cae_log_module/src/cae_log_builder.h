#pragma once

#include <cstdint>
#include <map>
#include <string>
#include <utility>

#include "cae_logger_export.h"
#include "cae_logger_types.h"

#include <spdlog/fmt/fmt.h>

namespace cae
{

/**
 * \brief Fluent builder for structured CAE analysis events.
 *
 * A builder accumulates fields for one JSONL analysis event. Records are not
 * written until `submit()` is called. The common pattern is:
 * `CAE_LOG(Info).module("Solver").stage("Iteration").action("step").submit()`.
 */
class CAE_LOGGER_EXPORT LogBuilder
{
  public:

    //! Creates a builder for the specified severity level.
    explicit LogBuilder(Level theLevel);

    //! Sets the logical module or component name written as `component`.
    LogBuilder& module(const char* theModule);

    //! Sets the workflow stage name used for report grouping.
    LogBuilder& stage(const char* theStage);

    //! Sets the stable action name, such as `read_file` or `solve_step`.
    LogBuilder& action(const char* theAction);

    //! Sets the related object kind and caller-redacted object name.
    LogBuilder& object(const char* theObjectType, const char* theObjectName);

    //! Sets the schema entity kind and name used by reports.
    LogBuilder& entity(const char* theEntityType, const char* theEntityName);

    //! Overrides the automatically inferred schema event type.
    LogBuilder& event_type(EventType theEventType);

    //! Overrides the automatically inferred schema event phase.
    LogBuilder& phase(EventPhase thePhase);

    //! Overrides the automatically inferred engineering domain.
    LogBuilder& domain(Domain theDomain);

    //! Sets the result status, for example `started`, `completed`, or `failed`.
    LogBuilder& result(const char* theResult);

    //! Sets a stable failure, warning, skip, or degradation reason.
    LogBuilder& reason(const char* theReason);

    //! Adds an integer metric. Metric keys should use snake_case and include units when relevant.
    LogBuilder& metric(const char* theKey, std::int64_t theValue);

    //! Adds a floating-point metric.
    LogBuilder& metric(const char* theKey, double theValue);

    //! Adds a boolean metric.
    LogBuilder& metric(const char* theKey, bool theValue);

    //! Adds a string metric.
    LogBuilder& metric(const char* theKey, const std::string& theValue);

    //! Adds a UTF-8 string literal metric.
    LogBuilder& metric(const char* theKey, const char* theValue);

    //! Sets the top-level duration in microseconds and emits the event as a span.
    LogBuilder& duration_us(std::uint64_t theDurationUs);

    /**
     * \brief Formats and stores the human-readable event message.
     *
     * Machine-readable values should be added with structured setters such as
     * `stage()`, `action()`, `result()`, `reason()`, and `metric()`.
     */
    template<typename... Args>
    LogBuilder& message(fmt::format_string<Args...> theFormat, Args&&... theArgs)
    {
        myMessage = fmt::format(theFormat, std::forward<Args>(theArgs)...);
        return *this;
    }

    //! Submits the configured structured event to the global logger.
    void submit() const;

  private:

    Level                              myLevel;
    std::string                        myModule;
    std::string                        myStage;
    std::string                        myAction;
    std::string                        myObjectType;
    std::string                        myObjectName;
    std::string                        myEntityType;
    std::string                        myEntityName;
    EventType                          myEventType = EventType::Unknown;
    EventPhase                         myPhase = EventPhase::Unknown;
    Domain                             myDomain = Domain::Unknown;
    std::string                        myResult;
    std::string                        myReason;
    std::map<std::string, MetricValue> myMetrics;
    std::string                        myMessage;
    std::uint64_t                      myDurationUs = 0;
    bool                               myHasDuration = false;
};

} // namespace cae
