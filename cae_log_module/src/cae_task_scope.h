#pragma once

#include <memory>
#include <string>

#include "cae_logger_export.h"
#include "cae_logger_types.h"

namespace cae
{

struct TaskScopeState;

/**
 * \brief Emits a structured span event for a workflow scope.
 *
 * `TaskScope` models a real business lifecycle, such as geometry import,
 * meshing, solving, or export. Construction pushes span context; destruction
 * emits the completed span unless `cancel()` was called.
 */
class CAE_LOGGER_EXPORT TaskScope
{
  public:

    //! Starts a scope using the module and stage names; the action defaults to the stage.
    TaskScope(const char* theModule, const char* theStage, Level theLevel = Level::Info);

    //! Starts a scope with an explicit action name.
    TaskScope(const char* theModule, const char* theStage, Level theLevel, std::string theAction);

    //! Starts a scope with an explicit action and trace identifier.
    TaskScope(const char* theModule,
              const char* theStage,
              Level       theLevel,
              std::string theAction,
              std::string theTraceId);

    //! Emits the completion span unless the scope was cancelled.
    ~TaskScope() noexcept;

    TaskScope(const TaskScope&) = delete;
    TaskScope& operator=(const TaskScope&) = delete;

    //! Cancels emission and pops the scope context without writing a completion span.
    void cancel() noexcept;

  private:

    std::unique_ptr<TaskScopeState> myState;
};

} // namespace cae
