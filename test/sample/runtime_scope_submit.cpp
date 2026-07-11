#include "cae_logger.h"

#include <chrono>
#include <cstdint>
#include <ctime>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>

#ifdef _WIN32
    #include <direct.h>
#else
    #include <sys/stat.h>
#endif

namespace {

std::string join_path(const std::string& left, const std::string& right) {
    if (left.empty()) {
        return right;
    }
    const char last = left[left.size() - 1];
    if (last == '/' || last == '\\') {
        return left + right;
    }
    return left + "/" + right;
}

void make_directory(const std::string& path) {
#ifdef _WIN32
    _mkdir(path.c_str());
#else
    mkdir(path.c_str(), 0777);
#endif
}

void require_true(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

std::string read_file(const std::string& path) {
    std::ifstream input(path.c_str(), std::ios::binary);
    if (!input.is_open()) {
        return std::string();
    }

    return std::string((std::istreambuf_iterator<char>(input)),
                       std::istreambuf_iterator<char>());
}

bool file_contains(const std::string& path, const std::string& needle) {
    return read_file(path).find(needle) != std::string::npos;
}

std::string line_containing(const std::string& path, const std::string& needle) {
    std::ifstream input(path.c_str(), std::ios::binary);
    if (!input.is_open()) {
        return std::string();
    }

    std::string line;
    while (std::getline(input, line)) {
        if (line.find(needle) != std::string::npos) {
            return line;
        }
    }
    return std::string();
}

std::string string_json_field(const std::string& line, const std::string& key) {
    const std::string marker = "\"" + key + "\":\"";
    const std::size_t start = line.find(marker);
    require_true(start != std::string::npos, "missing JSON string field: " + key);

    const std::size_t value_begin = start + marker.size();
    const std::size_t value_end = line.find('"', value_begin);
    require_true(value_end != std::string::npos, "unterminated JSON string field: " + key);
    return line.substr(value_begin, value_end - value_begin);
}

std::uint64_t unsigned_json_field(const std::string& line, const std::string& key) {
    const std::string marker = "\"" + key + "\":";
    const std::size_t start = line.find(marker);
    require_true(start != std::string::npos, "missing JSON field: " + key);

    std::size_t value_begin = start + marker.size();
    while (value_begin < line.size() && line[value_begin] == ' ') {
        ++value_begin;
    }

    std::size_t value_end = value_begin;
    while (value_end < line.size() && line[value_end] >= '0' && line[value_end] <= '9') {
        ++value_end;
    }

    require_true(value_end > value_begin, "JSON field is not an unsigned integer: " + key);
    return static_cast<std::uint64_t>(std::stoull(line.substr(value_begin, value_end - value_begin)));
}

std::string text_log_path(const std::string& log_dir, const std::string& module) {
    return join_path(log_dir, module + ".log");
}

std::string analysis_log_path(const std::string& log_dir) {
    return join_path(log_dir, "cae_events.jsonl");
}

cae::LoggerOptions make_options(const std::string& log_dir) {
    cae::LoggerOptions options;
    options.thread_model = cae::ThreadModel::MultiThread;
    options.process_model = cae::ProcessModel::SingleProcess;
    options.io_mode = cae::IOMode::Sync;
    options.enable_console = false;
    options.enable_text_log = true;
    options.enable_analysis_log = true;
    options.truncate_file = true;
    options.min_level = cae::Level::Trace;
    options.flush_level = cae::Level::Error;
    options.flush_each_record = true;
    options.log_dir = log_dir;
    options.analysis_log_name = "cae_events.jsonl";
    options.global_pattern = "%v";
    options.logger_health_interval_events = 0;
    options.enable_call_chain_analysis = false;
    return options;
}

void tiny_work() {
    std::this_thread::sleep_for(std::chrono::milliseconds(2));
}

void test_submitted_scope_keeps_elapsed_time(const std::string& base_dir) {
    const std::string log_dir = join_path(base_dir, "scope_submit");
    make_directory(log_dir);

    const std::string submitted_message = "scope_with_submit_records_elapsed_time";
    const std::string submitted_child_message = "scope_with_submit_child_inherits_parent";
    const std::string text_log = text_log_path(log_dir, "ScopeSubmit");
    const std::string analysis_log = analysis_log_path(log_dir);

    cae::init(make_options(log_dir));
    std::string submitted_child_parent_span_id;
    std::string submitted_child_trace_id;
    {
        CAE_LOG_SCOPE(Info)
            .module("ScopeSubmit")
            .message(submitted_message)
            .submit();
        tiny_work();
        CAE_LOG(Info)
            .module("ScopeSubmit")
            .message(submitted_child_message)
            .submit();
        const std::string submitted_child_line =
            line_containing(analysis_log, submitted_child_message);
        require_true(!submitted_child_line.empty(),
                     "event inside a submitted scope should be present in analysis log");
        submitted_child_parent_span_id =
            string_json_field(submitted_child_line, "parent_span_id");
        submitted_child_trace_id = string_json_field(submitted_child_line, "trace_id");
        require_true(!submitted_child_parent_span_id.empty(),
                     "event inside a submitted scope should have a parent span");
        require_true(!file_contains(text_log, submitted_message),
                     "CAE_LOG_SCOPE with submit should not write before its local block exits");
        require_true(line_containing(analysis_log, submitted_message).empty(),
                     "CAE_LOG_SCOPE with submit should not write analysis before its local block exits");
    }

    require_true(file_contains(text_log, submitted_message),
                 "CAE_LOG_SCOPE with submit should write a text record when its local block exits");
    const std::string submitted_text_line = line_containing(text_log, submitted_message);
    require_true(submitted_text_line.find("duration_us=") != std::string::npos,
                 "submitted scope text record should include duration_us");

    const std::string submitted_line = line_containing(analysis_log, submitted_message);
    require_true(!submitted_line.empty(), "submitted scope should be present in analysis log");
    require_true(string_json_field(submitted_line, "span_id") == submitted_child_parent_span_id,
                 "submitted scope span should be the child event parent");
    require_true(string_json_field(submitted_line, "trace_id") == submitted_child_trace_id,
                 "submitted scope and child event should share a trace ID");
    require_true(submitted_line.find("\"event_kind\":\"span\"") != std::string::npos,
                 "submitted scope should be written as a span event");
    require_true(unsigned_json_field(submitted_line, "duration_us") > 0,
                 "submitted scope should record elapsed time in duration_us");

    cae::shutdown();
}

} // namespace

int main() {
    const std::string base_dir = std::string("runtime_scope_submit_out_")
                               + std::to_string(static_cast<long long>(std::time(nullptr)));
    make_directory(base_dir);

    try {
        test_submitted_scope_keeps_elapsed_time(base_dir);
    } catch (const std::exception& error) {
        cae::shutdown();
        std::cerr << error.what() << std::endl;
        return 1;
    }

    return 0;
}
