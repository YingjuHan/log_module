#include "cae_logger.h"

#include "cae_logger_core.h"
#include "cae_logger_detail.h"

namespace cae
{

//=======================================================================
// function : init
// purpose  :
//=======================================================================
void init(const std::string& theConfigPath)
{
    LoggerOptions anOptions;
    if (!theConfigPath.empty())
    {
        anOptions = detail::load_options_from_file(theConfigPath);
    }

    detail::LoggerCore::instance().configure(anOptions);
    detail::LoggerCore::instance().set_config_path(theConfigPath);
}

//=======================================================================
// function : init
// purpose  :
//=======================================================================
void init(const LoggerOptions& theOptions)
{
    detail::LoggerCore::instance().configure(theOptions);
}

//=======================================================================
// function : load_options_from_file
// purpose  :
//=======================================================================
LoggerOptions load_options_from_file(const std::string& theConfigPath)
{
    return detail::normalize_options(detail::load_options_from_file(theConfigPath));
}

//=======================================================================
// function : get_options
// purpose  :
//=======================================================================
LoggerOptions get_options()
{
    return detail::LoggerCore::instance().options();
}

//=======================================================================
// function : update_options
// purpose  :
//=======================================================================
void update_options(const LoggerOptions& theOptions)
{
    detail::LoggerCore::instance().update_options(theOptions);
}

//=======================================================================
// function : set_session
// purpose  :
//=======================================================================
void set_session(const std::string& theSessionId)
{
    detail::LoggerCore::instance().set_session(theSessionId);
}

//=======================================================================
// function : set_thread_name
// purpose  :
//=======================================================================
void set_thread_name(const std::string& theThreadName)
{
    detail::set_thread_name_context(theThreadName);
}

//=======================================================================
// function : set_node_id
// purpose  :
//=======================================================================
void set_node_id(const std::string& theNodeId)
{
    detail::set_node_id_context(theNodeId);
}

//=======================================================================
// function : set_mpi_rank
// purpose  :
//=======================================================================
void set_mpi_rank(optional<std::int32_t> theMpiRank)
{
    detail::set_mpi_rank_context(theMpiRank);
}

//=======================================================================
// function : set_mpi_rank
// purpose  :
//=======================================================================
void set_mpi_rank(std::int32_t theMpiRank)
{
    detail::set_mpi_rank_context(optional<std::int32_t>(theMpiRank));
}

//=======================================================================
// function : clear_mpi_rank
// purpose  :
//=======================================================================
void clear_mpi_rank()
{
    detail::set_mpi_rank_context(nullopt);
}

//=======================================================================
// function : set_job_id
// purpose  :
//=======================================================================
void set_job_id(const std::string& theJobId)
{
    detail::LoggerCore::instance().set_job_id(theJobId);
}

//=======================================================================
// function : set_logical_time
// purpose  :
//=======================================================================
void set_logical_time(std::uint64_t theLogicalTime)
{
    detail::set_logical_time_context(theLogicalTime);
}

//=======================================================================
// function : get_thread_name
// purpose  :
//=======================================================================
std::string get_thread_name()
{
    return detail::default_thread_name();
}

//=======================================================================
// function : capture_call_chain
// purpose  :
//=======================================================================
std::vector<CallChainFrame> capture_call_chain(std::size_t theMaxDepth, std::size_t theSkip)
{
    return detail::capture_call_chain_impl(theMaxDepth, theSkip, true);
}

//=======================================================================
// function : format_call_chain
// purpose  :
//=======================================================================
std::string format_call_chain(const std::vector<CallChainFrame>& theFrames)
{
    return detail::call_chain_summary(theFrames);
}

//=======================================================================
// function : get_trace_id
// purpose  :
//=======================================================================
std::string get_trace_id()
{
    return detail::LoggerCore::instance().current_trace_id();
}

//=======================================================================
// function : make_log_builder
// purpose  :
//=======================================================================
LogBuilder make_log_builder(Level theLevel)
{
    return LogBuilder(theLevel);
}

//=======================================================================
// function : shutdown
// purpose  :
//=======================================================================
void shutdown()
{
    detail::LoggerCore::instance().shutdown();
}

} // namespace cae
