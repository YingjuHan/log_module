#include "cae_logger_detail.h"

#include <spdlog/details/os.h>
#include <spdlog/fmt/fmt.h>

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <limits>
#include <random>
#include <type_traits>
#include <utility>

#ifndef CAE_LOGGER_ENABLE_STACKTRACE
    #define CAE_LOGGER_ENABLE_STACKTRACE 1
#endif

#ifdef _WIN32
    #include <psapi.h>
    #include <windows.h>
#endif

#if defined(__has_include)
    #if CAE_LOGGER_ENABLE_STACKTRACE && __has_include(<boost/stacktrace.hpp>)
        #define CAE_HAS_BOOST_STACKTRACE 1
        #include <boost/stacktrace.hpp>
    #else
        #define CAE_HAS_BOOST_STACKTRACE 0
    #endif
#else
    #define CAE_HAS_BOOST_STACKTRACE 0
#endif

namespace cae
{
namespace detail
{
    namespace
    {

        thread_local std::string              THE_THREAD_NAME;
        thread_local std::string              THE_NODE_ID;
        thread_local optional<std::int32_t>   THE_MPI_RANK;
        thread_local optional<std::uint64_t>  THE_LOGICAL_TIME;
        thread_local std::vector<ContextFrame> THE_CONTEXT_STACK;

        //=======================================================================
        // function : random_hex_64
        // purpose  :
        //=======================================================================
        std::string random_hex_64()
        {
            thread_local std::mt19937_64 aGenerator(static_cast<std::uint64_t>(std::random_device{}())
                                                    ^ (static_cast<std::uint64_t>(current_pid()) << 32)
                                                    ^ static_cast<std::uint64_t>(current_tid()));
            return fmt::format("{:016x}", aGenerator());
        }

        //=======================================================================
        // function : is_logger_internal_frame
        // purpose  :
        //=======================================================================
        bool is_logger_internal_frame(const std::string& theFunctionName)
        {
            static constexpr const char* THE_INTERNAL_MARKERS[] = {"cae::detail::LoggerCore::",
                                                                   "cae::LoggerCore::",
                                                                   "cae::LogBuilder::submit",
                                                                   "cae::capture_call_chain",
                                                                   "capture_call_chain_impl",
                                                                   "boost::stacktrace::",
                                                                   "boost::stacktrace_detail::"};

            for (const char* aMarker : THE_INTERNAL_MARKERS)
            {
                if (theFunctionName.find(aMarker) != std::string::npos)
                {
                    return true;
                }
            }

            return false;
        }

        //=======================================================================
        // function : environment_variable
        // purpose  :
        //=======================================================================
        std::string environment_variable(const char* theName)
        {
#ifdef _WIN32
            char*       aValue = nullptr;
            std::size_t aValueLength = 0;
            if (_dupenv_s(&aValue, &aValueLength, theName) == 0 && aValue != nullptr)
            {
                const std::string aResult(aValue);
                std::free(aValue);
                return aResult;
            }

            return "";
#else
            const char* aValue = std::getenv(theName);
            return aValue != nullptr ? aValue : "";
#endif
        }

    } // namespace

    //=======================================================================
    // function : trim
    // purpose  :
    //=======================================================================
    std::string trim(std::string theValue)
    {
        const auto aFirst = theValue.find_first_not_of(" \t\r\n");
        if (aFirst == std::string::npos)
        {
            return "";
        }

        const auto aLast = theValue.find_last_not_of(" \t\r\n");
        return theValue.substr(aFirst, aLast - aFirst + 1);
    }

    //=======================================================================
    // function : lower_copy
    // purpose  :
    //=======================================================================
    std::string lower_copy(std::string theValue)
    {
        std::transform(theValue.begin(),
                       theValue.end(),
                       theValue.begin(),
                       [](unsigned char theChar)
                       {
                           return static_cast<char>(std::tolower(theChar));
                       });
        return theValue;
    }

    //=======================================================================
    // function : unquote
    // purpose  :
    //=======================================================================
    std::string unquote(std::string theValue)
    {
        theValue = trim(std::move(theValue));
        if (theValue.size() >= 2 && theValue.front() == '"' && theValue.back() == '"')
        {
            return theValue.substr(1, theValue.size() - 2);
        }

        return theValue;
    }

    //=======================================================================
    // function : parse_bool
    // purpose  :
    //=======================================================================
    bool parse_bool(const std::string& theValue, bool theDefaultValue)
    {
        const std::string aLowered = lower_copy(trim(theValue));
        if (aLowered == "true" || aLowered == "1" || aLowered == "yes" || aLowered == "on")
        {
            return true;
        }

        if (aLowered == "false" || aLowered == "0" || aLowered == "no" || aLowered == "off")
        {
            return false;
        }

        return theDefaultValue;
    }

    //=======================================================================
    // function : parse_size
    // purpose  :
    //=======================================================================
    std::size_t parse_size(const std::string& theValue, std::size_t theDefaultValue)
    {
        try
        {
            const std::string aTrimmed = trim(theValue);
            if (aTrimmed.empty() || aTrimmed[0] == '-')
            {
                return theDefaultValue;
            }

            std::size_t       aParsedLength = 0;
            const auto        aParsed = std::stoull(aTrimmed, &aParsedLength);
            if (aParsedLength != aTrimmed.size())
            {
                return theDefaultValue;
            }
            if (aParsed > static_cast<unsigned long long>(std::numeric_limits<std::size_t>::max()))
            {
                return theDefaultValue;
            }

            return static_cast<std::size_t>(aParsed);
        }
        catch (...)
        {
            return theDefaultValue;
        }
    }

    //=======================================================================
    // function : parse_level
    // purpose  :
    //=======================================================================
    Level parse_level(const std::string& theValue, Level theDefaultValue)
    {
        const std::string aLowered = lower_copy(trim(theValue));
        if (aLowered == "trace")
        {
            return Level::Trace;
        }
        if (aLowered == "debug")
        {
            return Level::Debug;
        }
        if (aLowered == "info")
        {
            return Level::Info;
        }
        if (aLowered == "warn" || aLowered == "warning")
        {
            return Level::Warn;
        }
        if (aLowered == "error" || aLowered == "err")
        {
            return Level::Error;
        }
        if (aLowered == "critical" || aLowered == "fatal")
        {
            return Level::Critical;
        }

        return theDefaultValue;
    }

    //=======================================================================
    // function : parse_thread_model
    // purpose  :
    //=======================================================================
    ThreadModel parse_thread_model(const std::string& theValue, ThreadModel theDefaultValue)
    {
        const std::string aLowered = lower_copy(trim(theValue));
        if (aLowered == "st" || aLowered == "singlethread" || aLowered == "single_thread")
        {
            return ThreadModel::SingleThread;
        }
        if (aLowered == "mt" || aLowered == "multithread" || aLowered == "multi_thread")
        {
            return ThreadModel::MultiThread;
        }

        return theDefaultValue;
    }

    //=======================================================================
    // function : parse_process_model
    // purpose  :
    //=======================================================================
    ProcessModel parse_process_model(const std::string& theValue, ProcessModel theDefaultValue)
    {
        const std::string aLowered = lower_copy(trim(theValue));
        if (aLowered == "sp" || aLowered == "singleprocess" || aLowered == "single_process")
        {
            return ProcessModel::SingleProcess;
        }
        if (aLowered == "mp" || aLowered == "multiprocess" || aLowered == "multi_process")
        {
            return ProcessModel::MultiProcess;
        }

        return theDefaultValue;
    }

    //=======================================================================
    // function : parse_io_mode
    // purpose  :
    //=======================================================================
    IOMode parse_io_mode(const std::string& theValue, IOMode theDefaultValue)
    {
        const std::string aLowered = lower_copy(trim(theValue));
        if (aLowered == "sync" || aLowered == "synchronous")
        {
            return IOMode::Sync;
        }
        if (aLowered == "async" || aLowered == "asynchronous")
        {
            return IOMode::Async;
        }

        return theDefaultValue;
    }

    //=======================================================================
    // function : parse_async_overflow_policy
    // purpose  :
    //=======================================================================
    AsyncOverflowPolicy parse_async_overflow_policy(const std::string& theValue, AsyncOverflowPolicy theDefaultValue)
    {
        const std::string aLowered = lower_copy(trim(theValue));
        if (aLowered == "block" || aLowered == "blocking")
        {
            return AsyncOverflowPolicy::Block;
        }
        if (aLowered == "overrun_oldest" || aLowered == "overrunoldest" || aLowered == "drop_oldest")
        {
            return AsyncOverflowPolicy::OverrunOldest;
        }

        return theDefaultValue;
    }

    //=======================================================================
    // function : parse_double
    // purpose  :
    //=======================================================================
    double parse_double(const std::string& theValue, double theDefaultValue)
    {
        try
        {
            const std::string aTrimmed = trim(theValue);
            std::size_t       aParsedLength = 0;
            const double      aParsed = std::stod(aTrimmed, &aParsedLength);
            if (aParsedLength != aTrimmed.size() || !std::isfinite(aParsed))
            {
                return theDefaultValue;
            }

            return aParsed;
        }
        catch (...)
        {
            return theDefaultValue;
        }
    }

    //=======================================================================
    // function : to_spdlog_level
    // purpose  :
    //=======================================================================
    spdlog::level::level_enum to_spdlog_level(Level theLevel)
    {
        switch (theLevel)
        {
            case Level::Trace: return spdlog::level::trace;
            case Level::Debug: return spdlog::level::debug;
            case Level::Info: return spdlog::level::info;
            case Level::Warn: return spdlog::level::warn;
            case Level::Error: return spdlog::level::err;
            case Level::Critical: return spdlog::level::critical;
            default: return spdlog::level::info;
        }
    }

    //=======================================================================
    // function : to_spdlog_overflow_policy
    // purpose  :
    //=======================================================================
    spdlog::async_overflow_policy to_spdlog_overflow_policy(AsyncOverflowPolicy thePolicy)
    {
        switch (thePolicy)
        {
            case AsyncOverflowPolicy::OverrunOldest: return spdlog::async_overflow_policy::overrun_oldest;
            case AsyncOverflowPolicy::Block:
            default: return spdlog::async_overflow_policy::block;
        }
    }

    //=======================================================================
    // function : async_overflow_policy_to_string
    // purpose  :
    //=======================================================================
    const char* async_overflow_policy_to_string(AsyncOverflowPolicy thePolicy)
    {
        switch (thePolicy)
        {
            case AsyncOverflowPolicy::OverrunOldest: return "overrun_oldest";
            case AsyncOverflowPolicy::Block:
            default: return "block";
        }
    }

    //=======================================================================
    // function : level_to_string
    // purpose  :
    //=======================================================================
    const char* level_to_string(Level theLevel)
    {
        switch (theLevel)
        {
            case Level::Trace: return "TRACE";
            case Level::Debug: return "DEBUG";
            case Level::Info: return "INFO";
            case Level::Warn: return "WARN";
            case Level::Error: return "ERROR";
            case Level::Critical: return "CRITICAL";
            default: return "INFO";
        }
    }

    //=======================================================================
    // function : metric_counter
    // purpose  :
    //=======================================================================
    std::int64_t metric_counter(std::uint64_t theValue)
    {
        const auto aMaxValue = static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max());
        if (theValue > aMaxValue)
        {
            return std::numeric_limits<std::int64_t>::max();
        }

        return static_cast<std::int64_t>(theValue);
    }

    //=======================================================================
    // function : clamp_duration
    // purpose  :
    //=======================================================================
    std::uint64_t clamp_duration(std::uint64_t theDurationUs)
    {
        return std::max<std::uint64_t>(theDurationUs, 1);
    }

    //=======================================================================
    // function : event_kind_to_string
    // purpose  :
    //=======================================================================
    const char* event_kind_to_string(EventKind theEventKind)
    {
        switch (theEventKind)
        {
            case EventKind::Point: return "point";
            case EventKind::Span: return "span";
            default: return "point";
        }
    }

    //=======================================================================
    // function : event_type_to_string
    // purpose  :
    //=======================================================================
    const char* event_type_to_string(EventType theEventType)
    {
        switch (theEventType)
        {
            case EventType::Geometry: return "geometry";
            case EventType::Mesh: return "mesh";
            case EventType::Solve: return "solve";
            case EventType::IO: return "io";
            case EventType::UI: return "ui";
            case EventType::MPI: return "mpi";
            case EventType::PostProcess: return "postprocess";
            case EventType::System: return "system";
            case EventType::Unknown:
            default: return "unknown";
        }
    }

    //=======================================================================
    // function : event_phase_to_string
    // purpose  :
    //=======================================================================
    const char* event_phase_to_string(EventPhase thePhase)
    {
        switch (thePhase)
        {
            case EventPhase::Start: return "start";
            case EventPhase::Progress: return "progress";
            case EventPhase::End: return "end";
            case EventPhase::Unknown:
            default: return "unknown";
        }
    }

    //=======================================================================
    // function : domain_to_string
    // purpose  :
    //=======================================================================
    const char* domain_to_string(Domain theDomain)
    {
        switch (theDomain)
        {
            case Domain::CFD: return "cfd";
            case Domain::FEM: return "fem";
            case Domain::Pre: return "pre";
            case Domain::Post: return "post";
            case Domain::System: return "system";
            case Domain::Unknown:
            default: return "unknown";
        }
    }

    //=======================================================================
    // function : current_pid
    // purpose  :
    //=======================================================================
    int current_pid()
    {
        return spdlog::details::os::pid();
    }

    //=======================================================================
    // function : current_tid
    // purpose  :
    //=======================================================================
    std::size_t current_tid()
    {
        return spdlog::details::os::thread_id();
    }

    //=======================================================================
    // function : set_thread_name_context
    // purpose  :
    //=======================================================================
    void set_thread_name_context(const std::string& theThreadName)
    {
        THE_THREAD_NAME = theThreadName;
    }

    //=======================================================================
    // function : set_node_id_context
    // purpose  :
    //=======================================================================
    void set_node_id_context(const std::string& theNodeId)
    {
        THE_NODE_ID = theNodeId;
    }

    //=======================================================================
    // function : set_mpi_rank_context
    // purpose  :
    //=======================================================================
    void set_mpi_rank_context(optional<std::int32_t> theMpiRank)
    {
        THE_MPI_RANK = theMpiRank;
    }

    //=======================================================================
    // function : set_logical_time_context
    // purpose  :
    //=======================================================================
    void set_logical_time_context(std::uint64_t theLogicalTime)
    {
        THE_LOGICAL_TIME = theLogicalTime;
    }

    //=======================================================================
    // function : current_mpi_rank
    // purpose  :
    //=======================================================================
    optional<std::int32_t> current_mpi_rank()
    {
        return THE_MPI_RANK;
    }

    //=======================================================================
    // function : current_logical_time
    // purpose  :
    //=======================================================================
    optional<std::uint64_t> current_logical_time()
    {
        return THE_LOGICAL_TIME;
    }

    //=======================================================================
    // function : default_thread_name
    // purpose  :
    //=======================================================================
    std::string default_thread_name()
    {
        if (!THE_THREAD_NAME.empty())
        {
            return THE_THREAD_NAME;
        }

        return "tid:" + std::to_string(current_tid());
    }

    //=======================================================================
    // function : detect_default_node_id
    // purpose  :
    //=======================================================================
    std::string detect_default_node_id()
    {
        if (!THE_NODE_ID.empty())
        {
            return THE_NODE_ID;
        }

        const std::string aComputerName = environment_variable("COMPUTERNAME");
        if (!aComputerName.empty())
        {
            return aComputerName;
        }

        const std::string aHostName = environment_variable("HOSTNAME");
        if (!aHostName.empty())
        {
            return aHostName;
        }

        return "unknown-node";
    }

    //=======================================================================
    // function : derive_stage_from_component
    // purpose  :
    //=======================================================================
    std::string derive_stage_from_component(const std::string& theComponent)
    {
        const auto aPosition = theComponent.find_last_of('.');
        if (aPosition == std::string::npos || aPosition + 1 >= theComponent.size())
        {
            return theComponent;
        }

        return theComponent.substr(aPosition + 1);
    }

    //=======================================================================
    // function : json_escape
    // purpose  :
    //=======================================================================
    std::string json_escape(const std::string& theValue)
    {
        std::string anOutput;
        anOutput.reserve(theValue.size());
        for (unsigned char aChar : theValue)
        {
            switch (aChar)
            {
                case '\\': anOutput += "\\\\"; break;
                case '"': anOutput += "\\\""; break;
                case '\b': anOutput += "\\b"; break;
                case '\f': anOutput += "\\f"; break;
                case '\n':
                case '\r':
                case '\t': anOutput += ' '; break;
                default:
                    if (aChar < 0x20)
                    {
                        anOutput += ' ';
                    }
                    else
                    {
                        anOutput += static_cast<char>(aChar);
                    }
                    break;
            }
        }

        return anOutput;
    }

    //=======================================================================
    // function : nullable_json_string
    // purpose  :
    //=======================================================================
    std::string nullable_json_string(const std::string& theValue)
    {
        if (theValue.empty())
        {
            return "null";
        }

        return "\"" + json_escape(theValue) + "\"";
    }

    //=======================================================================
    // function : localtime_for
    // purpose  :
    //=======================================================================
    std::tm localtime_for(SystemClock::time_point theTimePoint)
    {
        return spdlog::details::os::localtime(SystemClock::to_time_t(theTimePoint));
    }

    //=======================================================================
    // function : timestamp_iso8601
    // purpose  :
    //=======================================================================
    std::string timestamp_iso8601(SystemClock::time_point theTimePoint)
    {
        const std::tm aTime = localtime_for(theTimePoint);
        const auto    aMillis = std::chrono::duration_cast<std::chrono::milliseconds>(theTimePoint.time_since_epoch())
                           % 1000;
        return fmt::format("{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}.{:03d}",
                           aTime.tm_year + 1900,
                           aTime.tm_mon + 1,
                           aTime.tm_mday,
                           aTime.tm_hour,
                           aTime.tm_min,
                           aTime.tm_sec,
                           static_cast<int>(aMillis.count()));
    }

    //=======================================================================
    // function : timestamp_epoch_us
    // purpose  :
    //=======================================================================
    std::uint64_t timestamp_epoch_us(SystemClock::time_point theTimePoint)
    {
        return static_cast<std::uint64_t>(
            std::chrono::duration_cast<std::chrono::microseconds>(theTimePoint.time_since_epoch()).count());
    }

    //=======================================================================
    // function : infer_event_type
    // purpose  :
    //=======================================================================
    EventType infer_event_type(const std::string& theComponent, const std::string& theStage)
    {
        const std::string aText = lower_copy(theComponent + "." + theStage);
        if (aText.find("geometry") != std::string::npos)
        {
            return EventType::Geometry;
        }
        if (aText.find("mesh") != std::string::npos)
        {
            return EventType::Mesh;
        }
        if (aText.find("solver") != std::string::npos || aText.find("iteration") != std::string::npos)
        {
            return EventType::Solve;
        }
        if (aText.find("mpi") != std::string::npos || aText.find("partition") != std::string::npos)
        {
            return EventType::MPI;
        }
        if (aText.find("postprocess") != std::string::npos || aText.find("post_process") != std::string::npos)
        {
            return EventType::PostProcess;
        }
        if (aText.find("import") != std::string::npos || aText.find("output") != std::string::npos
            || aText.find("reader") != std::string::npos)
        {
            return EventType::IO;
        }
        if (aText.find("ui") != std::string::npos || aText.find("display") != std::string::npos
            || aText.find("interaction") != std::string::npos)
        {
            return EventType::UI;
        }
        if (aText.find("system") != std::string::npos || aText.find("workflow") != std::string::npos)
        {
            return EventType::System;
        }

        return EventType::Unknown;
    }

    //=======================================================================
    // function : infer_event_phase
    // purpose  :
    //=======================================================================
    EventPhase infer_event_phase(EventKind theEventKind, const std::string& theAction)
    {
        const std::string aLowered = lower_copy(theAction);
        if (aLowered.find("start") != std::string::npos || aLowered.find("begin") != std::string::npos)
        {
            return EventPhase::Start;
        }
        if (theEventKind == EventKind::Span || aLowered.find("complete") != std::string::npos
            || aLowered.find("end") != std::string::npos)
        {
            return EventPhase::End;
        }

        return EventPhase::Progress;
    }

    //=======================================================================
    // function : infer_domain
    // purpose  :
    //=======================================================================
    Domain infer_domain(EventType theEventType)
    {
        switch (theEventType)
        {
            case EventType::Geometry:
            case EventType::Mesh: return Domain::Pre;
            case EventType::Solve: return Domain::CFD;
            case EventType::PostProcess: return Domain::Post;
            case EventType::System: return Domain::System;
            default: return Domain::Unknown;
        }
    }

    //=======================================================================
    // function : with_pid_suffix
    // purpose  :
    //=======================================================================
    fs::path with_pid_suffix(const fs::path& theDirectory, const std::string& theFileName, ProcessModel theProcessModel)
    {
        if (theProcessModel != ProcessModel::MultiProcess)
        {
            return theDirectory / theFileName;
        }

        const fs::path    aPath(theFileName);
        const std::string aStem = aPath.stem().string();
        const std::string anExtension = aPath.extension().string();
        return theDirectory / fmt::format("{}_pid{}{}", aStem, current_pid(), anExtension);
    }

    //=======================================================================
    // function : normalize_options
    // purpose  :
    //=======================================================================
    LoggerOptions normalize_options(LoggerOptions theOptions)
    {
        if (theOptions.async_queue_size == 0)
        {
            theOptions.async_queue_size = 8192;
        }
        if (theOptions.async_thread_count == 0)
        {
            theOptions.async_thread_count = 1;
        }
        if (theOptions.log_dir.empty())
        {
            theOptions.log_dir = "logs";
        }
        if (theOptions.analysis_log_name.empty())
        {
            theOptions.analysis_log_name = "cae_events.jsonl";
        }
        if (theOptions.global_pattern.empty())
        {
            theOptions.global_pattern = "[%Y-%m-%d %H:%M:%S.%e] [%t] [%n] [%^%l%$] %v";
        }
        if (theOptions.call_chain_max_depth > 128)
        {
            theOptions.call_chain_max_depth = 128;
        }
        if (theOptions.call_chain_skip > 128)
        {
            theOptions.call_chain_skip = 128;
        }
        if (theOptions.call_chain_sample_rate < 0.0)
        {
            theOptions.call_chain_sample_rate = 0.0;
        }
        if (theOptions.call_chain_sample_rate > 1.0)
        {
            theOptions.call_chain_sample_rate = 1.0;
        }

        return theOptions;
    }

    //=======================================================================
    // function : load_options_from_file
    // purpose  :
    //=======================================================================
    LoggerOptions load_options_from_file(const std::string& theFilePath)
    {
        LoggerOptions anOptions;
        std::ifstream aFile(theFilePath);
        if (!aFile.is_open())
        {
            return anOptions;
        }

        std::string aLine;
        while (std::getline(aFile, aLine))
        {
            aLine = trim(aLine);
            if (aLine.empty() || aLine[0] == '#' || aLine[0] == ';')
            {
                continue;
            }

            const auto aPosition = aLine.find('=');
            if (aPosition == std::string::npos)
            {
                continue;
            }

            const std::string aKey = lower_copy(trim(aLine.substr(0, aPosition)));
            const std::string aValue = trim(aLine.substr(aPosition + 1));

            if (aKey == "thread_model")
            {
                anOptions.thread_model = parse_thread_model(aValue, anOptions.thread_model);
            }
            else if (aKey == "process_model")
            {
                anOptions.process_model = parse_process_model(aValue, anOptions.process_model);
            }
            else if (aKey == "io_mode")
            {
                anOptions.io_mode = parse_io_mode(aValue, anOptions.io_mode);
            }
            else if (aKey == "truncate_file")
            {
                anOptions.truncate_file = parse_bool(aValue, anOptions.truncate_file);
            }
            else if (aKey == "async_queue_size")
            {
                anOptions.async_queue_size = parse_size(aValue, anOptions.async_queue_size);
            }
            else if (aKey == "async_thread_count")
            {
                anOptions.async_thread_count = parse_size(aValue, anOptions.async_thread_count);
            }
            else if (aKey == "async_overflow_policy")
            {
                anOptions.async_overflow_policy = parse_async_overflow_policy(aValue, anOptions.async_overflow_policy);
            }
            else if (aKey == "enable_lossy_drop_policy" || aKey == "lossy_drop_policy")
            {
                anOptions.enable_lossy_drop_policy = parse_bool(aValue, anOptions.enable_lossy_drop_policy);
            }
            else if (aKey == "lossy_drop_below_level" || aKey == "drop_below_level")
            {
                anOptions.lossy_drop_below_level = parse_level(aValue, anOptions.lossy_drop_below_level);
            }
            else if (aKey == "global_pattern")
            {
                anOptions.global_pattern = unquote(aValue);
            }
            else if (aKey == "log_dir")
            {
                anOptions.log_dir = unquote(aValue);
            }
            else if (aKey == "analysis_log_name")
            {
                anOptions.analysis_log_name = unquote(aValue);
            }
            else if (aKey == "analysis_log_max_bytes")
            {
                anOptions.analysis_log_max_bytes = parse_size(aValue, anOptions.analysis_log_max_bytes);
            }
            else if (aKey == "analysis_log_retention_files")
            {
                anOptions.analysis_log_retention_files = parse_size(aValue, anOptions.analysis_log_retention_files);
            }
            else if (aKey == "logger_health_interval_events")
            {
                anOptions.logger_health_interval_events = parse_size(aValue, anOptions.logger_health_interval_events);
            }
            else if (aKey == "job_id")
            {
                anOptions.job_id = unquote(aValue);
            }
            else if (aKey == "enable_console" || aKey == "console")
            {
                anOptions.enable_console = parse_bool(aValue, anOptions.enable_console);
            }
            else if (aKey == "enable_text_log" || aKey == "text_log")
            {
                anOptions.enable_text_log = parse_bool(aValue, anOptions.enable_text_log);
            }
            else if (aKey == "enable_analysis_log" || aKey == "analysis_log")
            {
                anOptions.enable_analysis_log = parse_bool(aValue, anOptions.enable_analysis_log);
            }
            else if (aKey == "min_level")
            {
                anOptions.min_level = parse_level(aValue, anOptions.min_level);
            }
            else if (aKey == "flush_level")
            {
                anOptions.flush_level = parse_level(aValue, anOptions.flush_level);
            }
            else if (aKey == "flush_each_record" || aKey == "immediate_flush" || aKey == "write_through_files")
            {
                anOptions.flush_each_record = parse_bool(aValue, anOptions.flush_each_record);
            }
            else if (aKey == "enable_call_chain_analysis" || aKey == "call_chain_analysis"
                     || aKey == "enable_stacktrace")
            {
                anOptions.enable_call_chain_analysis = parse_bool(aValue, anOptions.enable_call_chain_analysis);
            }
            else if (aKey == "call_chain_min_level" || aKey == "stacktrace_min_level")
            {
                anOptions.call_chain_min_level = parse_level(aValue, anOptions.call_chain_min_level);
            }
            else if (aKey == "call_chain_max_depth" || aKey == "stacktrace_depth")
            {
                anOptions.call_chain_max_depth = parse_size(aValue, anOptions.call_chain_max_depth);
            }
            else if (aKey == "call_chain_skip" || aKey == "stacktrace_skip")
            {
                anOptions.call_chain_skip = parse_size(aValue, anOptions.call_chain_skip);
            }
            else if (aKey == "call_chain_sample_rate" || aKey == "stacktrace_sample_rate")
            {
                anOptions.call_chain_sample_rate = parse_double(aValue, anOptions.call_chain_sample_rate);
            }
        }

        return anOptions;
    }

    //=======================================================================
    // function : generate_trace_id
    // purpose  :
    //=======================================================================
    std::string generate_trace_id()
    {
        return random_hex_64() + random_hex_64();
    }

    //=======================================================================
    // function : generate_span_id
    // purpose  :
    //=======================================================================
    std::string generate_span_id()
    {
        return random_hex_64();
    }

    //=======================================================================
    // function : should_sample_call_chain
    // purpose  :
    //=======================================================================
    bool should_sample_call_chain(double theSampleRate)
    {
        if (theSampleRate >= 1.0)
        {
            return true;
        }
        if (theSampleRate <= 0.0)
        {
            return false;
        }

        thread_local std::mt19937_64           aGenerator(static_cast<std::uint64_t>(std::random_device{}())
                                                ^ (static_cast<std::uint64_t>(current_pid()) << 32)
                                                ^ static_cast<std::uint64_t>(current_tid()) ^ 0x9e3779b97f4a7c15ULL);
        std::uniform_real_distribution<double> aDistribution(0.0, 1.0);
        return aDistribution(aGenerator) < theSampleRate;
    }

    //=======================================================================
    // function : metric_value_to_json
    // purpose  :
    //=======================================================================
    std::string metric_value_to_json(const MetricValue& theValue)
    {
        switch (theValue.type())
        {
            case MetricValueType::String: return "\"" + json_escape(theValue.string_value()) + "\"";
            case MetricValueType::Boolean: return theValue.bool_value() ? "true" : "false";
            case MetricValueType::Integer: return std::to_string(theValue.integer_value());
            case MetricValueType::Double:
            default:
            {
                const double aDoubleValue = theValue.double_value();
                if (std::isnan(aDoubleValue))
                {
                    return "\"nan\"";
                }
                if (std::isinf(aDoubleValue))
                {
                    return std::signbit(aDoubleValue) ? "\"-inf\"" : "\"inf\"";
                }
                return fmt::format("{}", aDoubleValue);
            }
        }
    }

    //=======================================================================
    // function : metrics_to_json
    // purpose  :
    //=======================================================================
    std::string metrics_to_json(const std::map<std::string, MetricValue>& theMetrics)
    {
        std::string aJson = "{";
        bool        isFirst = true;
        for (std::map<std::string, MetricValue>::const_iterator anIt = theMetrics.begin();
             anIt != theMetrics.end();
             ++anIt)
        {
            if (!isFirst)
            {
                aJson += ",";
            }

            isFirst = false;
            aJson += fmt::format("\"{}\":{}", json_escape(anIt->first), metric_value_to_json(anIt->second));
        }

        aJson += "}";
        return aJson;
    }

    //=======================================================================
    // function : capture_call_chain_impl
    // purpose  :
    //=======================================================================
    std::vector<CallChainFrame> capture_call_chain_impl(std::size_t theMaxDepth,
                                                        std::size_t theSkip,
                                                        bool        theFilterLoggerInternalFrames)
    {
        std::vector<CallChainFrame> aFrames;
        if (theMaxDepth == 0)
        {
            return aFrames;
        }

#if CAE_HAS_BOOST_STACKTRACE
        const std::size_t             aCaptureDepth = std::min<std::size_t>(theMaxDepth + theSkip + 32, 256);
        boost::stacktrace::stacktrace aStackTrace(0, aCaptureDepth);
        std::size_t                   aSkippedExternalFrames = 0;

        for (std::size_t anIndex = 0; anIndex < aStackTrace.size() && aFrames.size() < theMaxDepth; ++anIndex)
        {
            const auto& aRawFrame = aStackTrace[anIndex];

            CallChainFrame aFrame;
            aFrame.index = aFrames.size();
            try
            {
                aFrame.function = aRawFrame.name();
                aFrame.source_file = aRawFrame.source_file();
                aFrame.source_line = static_cast<std::size_t>(aRawFrame.source_line());
                aFrame.address = fmt::format("0x{:x}", reinterpret_cast<std::uintptr_t>(aRawFrame.address()));
            }
            catch (...)
            {
                aFrame.function = "<unavailable>";
                aFrame.source_file.clear();
                aFrame.source_line = 0;
                aFrame.address.clear();
            }

            if (aFrame.function.empty())
            {
                aFrame.function = "<unknown>";
            }

            if (theFilterLoggerInternalFrames && is_logger_internal_frame(aFrame.function))
            {
                continue;
            }

            if (aSkippedExternalFrames < theSkip)
            {
                ++aSkippedExternalFrames;
                continue;
            }

            aFrames.push_back(std::move(aFrame));
        }
#endif

        return aFrames;
    }

    //=======================================================================
    // function : call_chain_to_json
    // purpose  :
    //=======================================================================
    std::string call_chain_to_json(const std::vector<CallChainFrame>& theFrames)
    {
        std::string aJson = "[";
        bool        isFirst = true;
        for (const auto& aFrame : theFrames)
        {
            if (!isFirst)
            {
                aJson += ",";
            }

            isFirst = false;
            aJson += fmt::format("{{\"index\":{},\"function\":\"{}\",\"source_file\":{},"
                                 "\"source_line\":{},\"address\":{}}}",
                                 aFrame.index,
                                 json_escape(aFrame.function),
                                 nullable_json_string(aFrame.source_file),
                                 aFrame.source_line,
                                 nullable_json_string(aFrame.address));
        }

        aJson += "]";
        return aJson;
    }

    //=======================================================================
    // function : call_chain_summary
    // purpose  :
    //=======================================================================
    std::string call_chain_summary(const std::vector<CallChainFrame>& theFrames)
    {
        std::string aSummary;
        for (const auto& aFrame : theFrames)
        {
            if (!aSummary.empty())
            {
                aSummary += " -> ";
            }

            aSummary += aFrame.function.empty() ? "<unknown>" : aFrame.function;
        }

        return aSummary;
    }

    //=======================================================================
    // function : call_chain_status
    // purpose  :
    //=======================================================================
    const char* call_chain_status(bool theEnabled)
    {
        if (!theEnabled)
        {
            return "disabled";
        }

#if CAE_HAS_BOOST_STACKTRACE
        return "captured";
#else
        return "boost_stacktrace_unavailable";
#endif
    }

    //=======================================================================
    // function : format_call_chain_frame
    // purpose  :
    //=======================================================================
    std::string format_call_chain_frame(const CallChainFrame& theFrame)
    {
        std::string aLine = fmt::format("  #{} {}",
                                        theFrame.index,
                                        theFrame.function.empty() ? "<unknown>" : theFrame.function);
        if (!theFrame.source_file.empty())
        {
            if (theFrame.source_line > 0)
            {
                aLine += fmt::format(" [{}:{}]", theFrame.source_file, theFrame.source_line);
            }
            else
            {
                aLine += fmt::format(" [{}]", theFrame.source_file);
            }
        }
        if (!theFrame.address.empty())
        {
            aLine += fmt::format(" ({})", theFrame.address);
        }

        return aLine;
    }

    //=======================================================================
    // function : format_call_chain_block
    // purpose  :
    //=======================================================================
    std::string format_call_chain_block(const std::vector<CallChainFrame>& theFrames)
    {
        std::string aText;
        for (const auto& aFrame : theFrames)
        {
            aText += '\n';
            aText += format_call_chain_frame(aFrame);
        }

        return aText;
    }

    //=======================================================================
    // function : current_memory_mb
    // purpose  :
    //=======================================================================
    optional<double> current_memory_mb()
    {
#ifdef _WIN32
        PROCESS_MEMORY_COUNTERS_EX aCounters;
        std::memset(&aCounters, 0, sizeof(aCounters));
        aCounters.cb = sizeof(aCounters);
        if (GetProcessMemoryInfo(GetCurrentProcess(),
                                 reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&aCounters),
                                 sizeof(aCounters)))
        {
            return static_cast<double>(aCounters.WorkingSetSize) / (1024.0 * 1024.0);
        }
#endif

        return nullopt;
    }

    //=======================================================================
    // function : current_context_frame
    // purpose  :
    //=======================================================================
    const ContextFrame* current_context_frame()
    {
        if (THE_CONTEXT_STACK.empty())
        {
            return nullptr;
        }

        return &THE_CONTEXT_STACK.back();
    }

    //=======================================================================
    // function : push_scope_context
    // purpose  :
    //=======================================================================
    ScopeSeed push_scope_context(const std::string& theRequestedComponent,
                                 const std::string& theRequestedStage,
                                 const std::string& theRequestedAction,
                                 const std::string& theExplicitTraceId)
    {
        ScopeSeed aSeed;
        aSeed.component = theRequestedComponent.empty() ? "default" : theRequestedComponent;
        aSeed.stage = theRequestedStage.empty() ? derive_stage_from_component(aSeed.component) : theRequestedStage;
        aSeed.action = theRequestedAction.empty() ? "scope" : theRequestedAction;

        const ContextFrame* aCurrentFrame = current_context_frame();
        aSeed.trace_id = !theExplicitTraceId.empty()
                           ? theExplicitTraceId
                           : (aCurrentFrame != nullptr ? aCurrentFrame->trace_id : generate_trace_id());
        aSeed.parent_span_id = aCurrentFrame != nullptr ? aCurrentFrame->span_id : "";
        aSeed.span_id = generate_span_id();

        THE_CONTEXT_STACK.push_back(
            ContextFrame{aSeed.component, aSeed.stage, aSeed.action, aSeed.trace_id, aSeed.span_id});
        return aSeed;
    }

    //=======================================================================
    // function : pop_scope_context
    // purpose  :
    //=======================================================================
    void pop_scope_context(const std::string& theSpanId)
    {
        if (!THE_CONTEXT_STACK.empty() && THE_CONTEXT_STACK.back().span_id == theSpanId)
        {
            THE_CONTEXT_STACK.pop_back();
            return;
        }

        for (auto aReverseIt = THE_CONTEXT_STACK.rbegin(); aReverseIt != THE_CONTEXT_STACK.rend(); ++aReverseIt)
        {
            if (aReverseIt->span_id == theSpanId)
            {
                THE_CONTEXT_STACK.erase(std::next(aReverseIt).base());
                return;
            }
        }
    }

    //=======================================================================
    // function : default_scope_message
    // purpose  :
    //=======================================================================
    std::string default_scope_message(const std::string& theComponent,
                                      const std::string& theStage,
                                      const std::string& theAction)
    {
        if (!theAction.empty() && theAction != "scope" && theAction != "timed_scope")
        {
            return fmt::format("{} {} completed.", theStage, theAction);
        }

        return fmt::format("{} workflow completed for component {}.", theStage, theComponent);
    }

} // namespace detail
} // namespace cae
