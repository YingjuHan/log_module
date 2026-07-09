#pragma once

#include <memory>
#include <string>

#include "cae_logger_export.h"
#include "cae_logger_types.h"

namespace cae
{

struct ScopedTimerState;

/**
 * \brief Emits a timed span event for a scoped operation.
 *
 * `ScopedTimer` is intended for local code-block timing. Use `TaskScope` for
 * business workflow spans that need stable stage/action semantics.
 */
class CAE_LOGGER_EXPORT ScopedTimer
{
  public:

    //! Starts a timer for the specified module and message.
    ScopedTimer(const char* theModule, Level theLevel, std::string theMessage);

    //! Starts a timer for the specified module and message.
    ScopedTimer(std::string theModule, Level theLevel, std::string theMessage);

    //! Emits the elapsed-time span unless the timer was cancelled.
    ~ScopedTimer() noexcept;

    ScopedTimer(const ScopedTimer&) = delete;
    ScopedTimer& operator=(const ScopedTimer&) = delete;

    //! Cancels emission and pops the scope context without writing a span.
    void cancel() noexcept;

  private:

    std::unique_ptr<ScopedTimerState> myState;
};

} // namespace cae
