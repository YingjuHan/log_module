#include "cae_jsonl_analysis_printer.h"

#include <spdlog/fmt/fmt.h>

#include <algorithm>
#include <cctype>
#include <utility>

namespace cae
{
namespace detail
{

    //=======================================================================
    // function : JsonlAnalysisPrinter::JsonlAnalysisPrinter
    // purpose  :
    //=======================================================================
    JsonlAnalysisPrinter::JsonlAnalysisPrinter(LoggerOptions theOptions)
    : myOptions(std::move(theOptions)),
      myBasePath(with_pid_suffix(fs::path(myOptions.log_dir), myOptions.analysis_log_name, myOptions.process_model))
    {
        initialize_output_unlocked();
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::write
    // purpose  :
    //=======================================================================
    void JsonlAnalysisPrinter::write(const LogRecord& theRecord)
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        if (!myOut.is_open())
        {
            return;
        }

        const std::tm aTime = localtime_for(theRecord.timestamp);
        char          aDateBuffer[16];
        char          aTimeBuffer[16];
        std::strftime(aDateBuffer, sizeof(aDateBuffer), "%Y-%m-%d", &aTime);
        std::strftime(aTimeBuffer, sizeof(aTimeBuffer), "%H:%M:%S", &aTime);

        const std::string aSource = fmt::format("pid:{}/tid:{}", theRecord.pid, theRecord.tid);
        const std::string aLine =
            fmt::format("{{\"schema_version\":\"{}\",\"timestamp\":\"{}\","
                        "\"timestamp_epoch_us\":{},\"monotonic_us\":{},"
                        "\"date\":\"{}\",\"time\":\"{}\",\"source\":\"{}\","
                        "\"component\":\"{}\",\"stage\":\"{}\",\"action\":\"{}\","
                        "\"level\":\"{}\",\"message\":\"{}\",\"event_kind\":\"{}\","
                        "\"event_type\":\"{}\",\"phase\":\"{}\",\"domain\":\"{}\","
                        "\"entity_type\":\"{}\",\"entity_name\":\"{}\",\"duration_us\":{},"
                        "\"size\":{},\"session\":\"{}\",\"job_id\":\"{}\",\"thread_name\":\"{}\","
                        "\"sequence\":{},\"global_sequence_id\":\"{}\",\"logical_time\":{},"
                        "\"trace_id\":\"{}\",\"span_id\":\"{}\",\"event_id\":\"{}\","
                        "\"parent_span_id\":{},\"parent_event_id\":{},\"object_type\":{},"
                        "\"object_name\":{},\"result\":{},\"reason\":{},\"node_id\":\"{}\","
                        "\"mpi_rank\":{},\"metrics\":{},\"call_chain_status\":\"{}\","
                        "\"call_chain_summary\":{},\"call_chain\":{}}}\n",
                        kCaeEventSchemaVersion,
                        timestamp_iso8601(theRecord.timestamp),
                        theRecord.timestamp_epoch_us,
                        theRecord.monotonic_us,
                        aDateBuffer,
                        aTimeBuffer,
                        json_escape(aSource),
                        json_escape(theRecord.component),
                        json_escape(theRecord.stage),
                        json_escape(theRecord.action),
                        level_to_string(theRecord.level),
                        json_escape(theRecord.message),
                        event_kind_to_string(theRecord.event_kind),
                        json_escape(theRecord.event_type),
                        json_escape(theRecord.phase),
                        json_escape(theRecord.domain),
                        json_escape(theRecord.entity_type),
                        json_escape(theRecord.entity_name),
                        theRecord.event_kind == EventKind::Span ? clamp_duration(theRecord.duration_us) : 0,
                        theRecord.message.size(),
                        json_escape(theRecord.session),
                        json_escape(theRecord.job_id),
                        json_escape(theRecord.thread_name),
                        theRecord.sequence,
                        json_escape(theRecord.global_sequence_id),
                        theRecord.logical_time,
                        json_escape(theRecord.trace_id),
                        json_escape(theRecord.span_id),
                        json_escape(theRecord.event_id),
                        nullable_json_string(theRecord.parent_span_id),
                        nullable_json_string(theRecord.parent_event_id),
                        nullable_json_string(theRecord.object_type),
                        nullable_json_string(theRecord.object_name),
                        nullable_json_string(theRecord.result),
                        nullable_json_string(theRecord.reason),
                        json_escape(theRecord.node_id),
                        theRecord.mpi_rank.has_value() ? std::to_string(*theRecord.mpi_rank) : "null",
                        metrics_to_json(theRecord.metrics),
                        json_escape(theRecord.call_chain_status),
                        nullable_json_string(call_chain_summary(theRecord.call_chain)),
                        call_chain_to_json(theRecord.call_chain));

        rotate_if_needed_unlocked(aLine.size());
        if (!myOut.is_open())
        {
            return;
        }

        myOut << aLine;
        myBufferedBytes += aLine.size();
        myCurrentSegmentBytes += aLine.size();
        myAnalysisBytesWritten += aLine.size();
        if (myOptions.flush_each_record || theRecord.level >= myOptions.flush_level
            || myBufferedBytes >= kFlushThresholdBytes)
        {
            flush_unlocked();
        }
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::flush
    // purpose  :
    //=======================================================================
    void JsonlAnalysisPrinter::flush()
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        flush_unlocked();
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::close
    // purpose  :
    //=======================================================================
    void JsonlAnalysisPrinter::close()
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        if (myOut.is_open())
        {
            flush_unlocked();
            myOut.close();
        }
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::reload_options
    // purpose  :
    //=======================================================================
    void JsonlAnalysisPrinter::reload_options(const LoggerOptions& theOptions)
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        myOptions = theOptions;
        apply_retention_unlocked();
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::collect_stats
    // purpose  :
    //=======================================================================
    void JsonlAnalysisPrinter::collect_stats(LoggerRuntimeStats& theStats) const
    {
        std::lock_guard<std::mutex> aLock(myMutex);
        theStats.analysis_bytes_written += myAnalysisBytesWritten;
        theStats.analysis_segments_created += myAnalysisSegmentsCreated;
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::segment_path
    // purpose  :
    //=======================================================================
    fs::path JsonlAnalysisPrinter::segment_path(std::size_t theSegmentIndex) const
    {
        if (theSegmentIndex == 0)
        {
            return myBasePath;
        }

        const std::string aStem = myBasePath.stem().string();
        const std::string anExtension = myBasePath.extension().string();
        return myBasePath.parent_path() / fmt::format("{}_{:06d}{}", aStem, theSegmentIndex, anExtension);
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::matching_segments_unlocked
    // purpose  :
    //=======================================================================
    std::vector<std::pair<std::size_t, fs::path>> JsonlAnalysisPrinter::matching_segments_unlocked() const
    {
        std::vector<std::pair<std::size_t, fs::path>> aSegments;
        std::error_code                               anError;
        if (!fs::exists(myBasePath.parent_path(), anError))
        {
            return aSegments;
        }

        const std::vector<fs::path> aFiles = fs::regular_files(myBasePath.parent_path(), anError);
        for (std::vector<fs::path>::const_iterator anIt = aFiles.begin(); anIt != aFiles.end(); ++anIt)
        {
            if (anError)
            {
                continue;
            }

            std::size_t aSegmentIndex = 0;
            if (parse_segment_index(*anIt, aSegmentIndex))
            {
                aSegments.push_back(std::make_pair(aSegmentIndex, *anIt));
            }
        }

        std::sort(aSegments.begin(),
                  aSegments.end(),
                  [](const std::pair<std::size_t, fs::path>& theLeft,
                     const std::pair<std::size_t, fs::path>& theRight)
                  {
                      return theLeft.first < theRight.first;
                  });
        return aSegments;
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::remove_matching_segments_unlocked
    // purpose  :
    //=======================================================================
    void JsonlAnalysisPrinter::remove_matching_segments_unlocked()
    {
        for (const auto& aSegment : matching_segments_unlocked())
        {
            std::error_code aRemoveError;
            fs::remove(aSegment.second, aRemoveError);
        }
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::select_initial_segment_index_unlocked
    // purpose  :
    //=======================================================================
    std::size_t JsonlAnalysisPrinter::select_initial_segment_index_unlocked() const
    {
        const auto aSegments = matching_segments_unlocked();
        if (aSegments.empty())
        {
            return 0;
        }

        return aSegments.back().first;
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::next_unused_segment_index_unlocked
    // purpose  :
    //=======================================================================
    std::size_t JsonlAnalysisPrinter::next_unused_segment_index_unlocked(std::size_t theStartIndex) const
    {
        const auto  aSegments = matching_segments_unlocked();
        std::size_t aCandidate = theStartIndex;
        for (const auto& aSegment : aSegments)
        {
            if (aSegment.first < aCandidate)
            {
                continue;
            }
            if (aSegment.first == aCandidate)
            {
                ++aCandidate;
                continue;
            }

            break;
        }

        return aCandidate;
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::initialize_output_unlocked
    // purpose  :
    //=======================================================================
    void JsonlAnalysisPrinter::initialize_output_unlocked()
    {
        if (myOptions.truncate_file)
        {
            remove_matching_segments_unlocked();
            open_segment_unlocked(0, true);
            return;
        }

        open_segment_unlocked(select_initial_segment_index_unlocked(), false);
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::open_segment_unlocked
    // purpose  :
    //=======================================================================
    void JsonlAnalysisPrinter::open_segment_unlocked(std::size_t theSegmentIndex, bool theTruncate)
    {
        mySegmentIndex = theSegmentIndex;
        myPath = segment_path(mySegmentIndex);
        std::error_code anExistsError;
        const bool      hasExisted = fs::exists(myPath, anExistsError);
        const auto      anOpenMode = theTruncate ? (std::ios::out | std::ios::trunc) : (std::ios::out | std::ios::app);

        myOut.clear();
        myOut.open(myPath.c_str(), anOpenMode);
        myBufferedBytes = 0;
        myCurrentSegmentBytes = 0;
        if (!myOut.is_open())
        {
            return;
        }

        std::error_code aSizeError;
        const std::uint64_t aSize = fs::file_size(myPath, aSizeError);
        if (!aSizeError)
        {
            myCurrentSegmentBytes = static_cast<std::uint64_t>(aSize);
        }

        if (!hasExisted)
        {
            ++myAnalysisSegmentsCreated;
        }

        apply_retention_unlocked();
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::rotate_if_needed_unlocked
    // purpose  :
    //=======================================================================
    void JsonlAnalysisPrinter::rotate_if_needed_unlocked(std::size_t theNextLineBytes)
    {
        const std::uint64_t aMaxBytes = static_cast<std::uint64_t>(myOptions.analysis_log_max_bytes);
        if (aMaxBytes == 0 || myCurrentSegmentBytes == 0)
        {
            return;
        }
        if (myCurrentSegmentBytes + static_cast<std::uint64_t>(theNextLineBytes) <= aMaxBytes)
        {
            return;
        }

        flush_unlocked();
        myOut.close();
        open_segment_unlocked(next_unused_segment_index_unlocked(mySegmentIndex + 1), false);
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::parse_segment_index
    // purpose  :
    //=======================================================================
    bool JsonlAnalysisPrinter::parse_segment_index(const fs::path& theCandidate, std::size_t& theSegmentIndex) const
    {
        if (theCandidate.extension() != myBasePath.extension())
        {
            return false;
        }

        const std::string aStem = theCandidate.stem().string();
        const std::string aBaseStem = myBasePath.stem().string();
        if (aStem == aBaseStem)
        {
            theSegmentIndex = 0;
            return true;
        }

        const std::string aPrefix = aBaseStem + "_";
        if (aStem.rfind(aPrefix, 0) != 0)
        {
            return false;
        }

        const std::string aSuffix = aStem.substr(aPrefix.size());
        if (aSuffix.empty()
            || !std::all_of(aSuffix.begin(),
                            aSuffix.end(),
                            [](unsigned char theChar)
                            {
                                return std::isdigit(theChar) != 0;
                            }))
        {
            return false;
        }

        try
        {
            theSegmentIndex = static_cast<std::size_t>(std::stoull(aSuffix));
            return true;
        }
        catch (...)
        {
            return false;
        }
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::apply_retention_unlocked
    // purpose  :
    //=======================================================================
    void JsonlAnalysisPrinter::apply_retention_unlocked()
    {
        if (myOptions.analysis_log_retention_files == 0)
        {
            return;
        }

        const auto aSegments = matching_segments_unlocked();
        if (aSegments.size() <= myOptions.analysis_log_retention_files)
        {
            return;
        }

        const auto aRemoveCount = aSegments.size() - myOptions.analysis_log_retention_files;
        for (std::size_t anIndex = 0; anIndex < aRemoveCount; ++anIndex)
        {
            std::error_code aRemoveError;
            fs::remove(aSegments[anIndex].second, aRemoveError);
        }
    }

    //=======================================================================
    // function : JsonlAnalysisPrinter::flush_unlocked
    // purpose  :
    //=======================================================================
    void JsonlAnalysisPrinter::flush_unlocked()
    {
        if (myOut.is_open())
        {
            myOut.flush();
            myBufferedBytes = 0;
        }
    }

} // namespace detail
} // namespace cae
