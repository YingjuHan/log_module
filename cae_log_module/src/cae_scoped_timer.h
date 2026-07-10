#pragma once

#include <memory>
#include <string>
#include <utility>

#include "cae_logger_export.h"
#include "cae_logger_types.h"

#include <spdlog/fmt/fmt.h>

namespace cae
{

struct ScopedTimerState;

/**
 * \brief Emits a timed span event for a scoped operation.
 *
 * `ScopedTimer` is intended for local code-block timing. Call `submit()` after
 * the chained configuration to write the span when the scope exits. Use
 * `TaskScope` for business workflow spans that need stable stage/action
 * semantics.
 */
class CAE_LOGGER_EXPORT ScopedTimer
{
  public:

    //! Starts a timer at the specified level and configures it through chained setters.
    explicit ScopedTimer(Level theLevel);

    //! Starts a timer for the specified module and message.
    ScopedTimer(const char* theModule, Level theLevel, std::string theMessage);

    //! Starts a timer for the specified module and message.
    ScopedTimer(std::string theModule, Level theLevel, std::string theMessage);

    //! Emits the elapsed-time span on scope exit only after `submit()` was called.
    ~ScopedTimer() noexcept;

    ScopedTimer(const ScopedTimer&) = delete;
    ScopedTimer& operator=(const ScopedTimer&) = delete;

    //! Sets the module/component name for this scoped timer.
    ScopedTimer& module(const char* theModule);

    //! Sets the module/component name for this scoped timer.
    ScopedTimer& module(const std::string& theModule);

    //! Sets the human-readable message without formatting.
    ScopedTimer& message(const char* theMessage);

    //! Sets the human-readable message without formatting.
    ScopedTimer& message(std::string theMessage);

    //! Formats and stores the human-readable scoped timer message.
    template<typename... Args>
    ScopedTimer& message(fmt::format_string<Args...> theFormat, Args&&... theArgs)
    {
        return message(fmt::format(theFormat, std::forward<Args>(theArgs)...));
    }

    //! Arms this timer so its elapsed-time span is written when the scope exits.
    void submit() noexcept;

    //! Cancels emission and pops the scope context without writing a span.
    void cancel() noexcept;

  private:

    void ensure_scope_context();

    std::unique_ptr<ScopedTimerState> myState;
};

} // namespace cae
