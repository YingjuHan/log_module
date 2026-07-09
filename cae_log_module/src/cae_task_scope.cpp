#include "cae_task_scope.h"

#include "cae_logger_core.h"
#include "cae_logger_detail.h"

#include <chrono>
#include <utility>

namespace cae
{

struct TaskScopeState
{
    std::string               component;
    std::string               stage;
    std::string               action;
    std::string               trace_id;
    std::string               span_id;
    std::string               parent_span_id;
    Level                     level = Level::Info;
    detail::Clock::time_point start = detail::Clock::now();
    bool                      is_active = true;
};

//=======================================================================
// function : TaskScope::TaskScope
// purpose  :
//=======================================================================
TaskScope::TaskScope(const char* theModule, const char* theStage, Level theLevel)
: TaskScope(theModule, theStage, theLevel, "", "")
{
}

//=======================================================================
// function : TaskScope::TaskScope
// purpose  :
//=======================================================================
TaskScope::TaskScope(const char* theModule, const char* theStage, Level theLevel, std::string theAction)
: TaskScope(theModule, theStage, theLevel, std::move(theAction), "")
{
}

//=======================================================================
// function : TaskScope::TaskScope
// purpose  :
//=======================================================================
TaskScope::TaskScope(const char* theModule,
                     const char* theStage,
                     Level       theLevel,
                     std::string theAction,
                     std::string theTraceId)
: myState(std::unique_ptr<TaskScopeState>(new TaskScopeState()))
{
    const detail::ScopeSeed aSeed = detail::push_scope_context(theModule != nullptr ? theModule : "",
                                                               theStage != nullptr ? theStage : "",
                                                               theAction,
                                                               theTraceId);
    myState->component = aSeed.component;
    myState->stage = aSeed.stage;
    myState->action = aSeed.action;
    myState->trace_id = aSeed.trace_id;
    myState->span_id = aSeed.span_id;
    myState->parent_span_id = aSeed.parent_span_id;
    myState->level = theLevel;
    myState->start = detail::Clock::now();
}

//=======================================================================
// function : TaskScope::~TaskScope
// purpose  :
//=======================================================================
TaskScope::~TaskScope() noexcept
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
    const Level       aLevel = myState->level;
    detail::pop_scope_context(aSpanId);

    try
    {
        detail::LoggerCore::instance().emit_scope_record(aComponent,
                                                         aStage,
                                                         anAction,
                                                         aLevel,
                                                         aDurationUs,
                                                         detail::default_scope_message(aComponent, aStage, anAction),
                                                         aTraceId,
                                                         aSpanId,
                                                         aParentSpanId);
    }
    catch (...)
    {
    }
}

//=======================================================================
// function : TaskScope::cancel
// purpose  :
//=======================================================================
void TaskScope::cancel() noexcept
{
    if (myState && myState->is_active)
    {
        myState->is_active = false;
        detail::pop_scope_context(myState->span_id);
    }
}

} // namespace cae
