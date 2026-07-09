#include "cae_scoped_timer.h"

#include "cae_logger_core.h"
#include "cae_logger_detail.h"

#include <chrono>
#include <utility>

namespace cae
{

struct ScopedTimerState
{
    std::string               component;
    std::string               stage;
    std::string               action;
    std::string               trace_id;
    std::string               span_id;
    std::string               parent_span_id;
    std::string               message;
    Level                     level = Level::Info;
    detail::Clock::time_point start = detail::Clock::now();
    bool                      is_active = true;
};

//=======================================================================
// function : ScopedTimer::ScopedTimer
// purpose  :
//=======================================================================
ScopedTimer::ScopedTimer(const char* theModule, Level theLevel, std::string theMessage)
: myState(std::unique_ptr<ScopedTimerState>(new ScopedTimerState()))
{
    const std::string       aModule = theModule != nullptr && *theModule != '\0' ? theModule : "default";
    const detail::ScopeSeed aSeed =
        detail::push_scope_context(aModule, detail::derive_stage_from_component(aModule), "timed_scope", "");
    myState->component = aSeed.component;
    myState->stage = aSeed.stage;
    myState->action = aSeed.action;
    myState->trace_id = aSeed.trace_id;
    myState->span_id = aSeed.span_id;
    myState->parent_span_id = aSeed.parent_span_id;
    myState->message = std::move(theMessage);
    myState->level = theLevel;
    myState->start = detail::Clock::now();
}

//=======================================================================
// function : ScopedTimer::ScopedTimer
// purpose  :
//=======================================================================
ScopedTimer::ScopedTimer(std::string theModule, Level theLevel, std::string theMessage)
: ScopedTimer(theModule.c_str(), theLevel, std::move(theMessage))
{
}

//=======================================================================
// function : ScopedTimer::~ScopedTimer
// purpose  :
//=======================================================================
ScopedTimer::~ScopedTimer() noexcept
{
    if (!myState || !myState->is_active)
    {
        return;
    }

    const auto anElapsed =
        std::chrono::duration_cast<std::chrono::microseconds>(detail::Clock::now() - myState->start).count();
    const auto        aDurationUs = anElapsed > 0 ? static_cast<std::uint64_t>(anElapsed) : 1;
    const std::string aComponent = myState->component;
    const std::string aStage = myState->stage;
    const std::string anAction = myState->action;
    const std::string aTraceId = myState->trace_id;
    const std::string aSpanId = myState->span_id;
    const std::string aParentSpanId = myState->parent_span_id;
    const std::string aMessage = myState->message;
    const Level       aLevel = myState->level;
    detail::pop_scope_context(aSpanId);

    try
    {
        detail::LoggerCore::instance().emit_scope_record(aComponent,
                                                         aStage,
                                                         anAction,
                                                         aLevel,
                                                         aDurationUs,
                                                         aMessage,
                                                         aTraceId,
                                                         aSpanId,
                                                         aParentSpanId);
    }
    catch (...)
    {
    }
}

//=======================================================================
// function : ScopedTimer::cancel
// purpose  :
//=======================================================================
void ScopedTimer::cancel() noexcept
{
    if (myState && myState->is_active)
    {
        myState->is_active = false;
        detail::pop_scope_context(myState->span_id);
    }
}

} // namespace cae
