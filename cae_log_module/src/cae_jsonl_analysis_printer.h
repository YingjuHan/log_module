#pragma once

#include <fstream>
#include <mutex>
#include <utility>
#include <vector>

#include "cae_printer.h"

namespace cae
{
namespace detail
{

    class JsonlAnalysisPrinter final : public Printer
    {
      public:

        static constexpr std::size_t kFlushThresholdBytes = 64 * 1024;

      public:

        explicit JsonlAnalysisPrinter(LoggerOptions theOptions);

        void write(const LogRecord& theRecord) override;
        void flush() override;
        void close() override;
        void reload_options(const LoggerOptions& theOptions) override;
        void collect_stats(LoggerRuntimeStats& theStats) const override;

      private:

        fs::path                                      segment_path(std::size_t theSegmentIndex) const;
        std::vector<std::pair<std::size_t, fs::path>> matching_segments_unlocked() const;
        void                                                       remove_matching_segments_unlocked();
        std::size_t                                                select_initial_segment_index_unlocked() const;
        std::size_t next_unused_segment_index_unlocked(std::size_t theStartIndex) const;
        void        initialize_output_unlocked();
        void        open_segment_unlocked(std::size_t theSegmentIndex, bool theTruncate);
        void        rotate_if_needed_unlocked(std::size_t theNextLineBytes);
        bool        parse_segment_index(const fs::path& theCandidate, std::size_t& theSegmentIndex) const;
        void        apply_retention_unlocked();
        void        flush_unlocked();

      private:

        LoggerOptions      myOptions;
        fs::path           myBasePath;
        fs::path           myPath;
        mutable std::mutex myMutex;
        std::ofstream      myOut;
        std::size_t        myBufferedBytes = 0;
        std::size_t        mySegmentIndex = 0;
        std::uint64_t      myCurrentSegmentBytes = 0;
        std::uint64_t      myAnalysisBytesWritten = 0;
        std::uint64_t      myAnalysisSegmentsCreated = 0;
    };

} // namespace detail
} // namespace cae
