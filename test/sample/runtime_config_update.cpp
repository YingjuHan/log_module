#include "cae_logger.h"

#include <ctime>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

#ifdef _WIN32
    #include <direct.h>
    #include <windows.h>
#else
    #include <sys/stat.h>
    #include <unistd.h>
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

void sleep_milliseconds(unsigned long milliseconds) {
#ifdef _WIN32
    Sleep(milliseconds);
#else
    usleep(milliseconds * 1000);
#endif
}

bool file_contains(const std::string& path, const std::string& needle) {
    std::ifstream input(path.c_str(), std::ios::binary);
    if (!input.is_open()) {
        return false;
    }

    const std::string content((std::istreambuf_iterator<char>(input)),
                              std::istreambuf_iterator<char>());
    return content.find(needle) != std::string::npos;
}

std::string text_log_path(const std::string& log_dir, const std::string& module) {
    return join_path(log_dir, module + ".log");
}

void write_config(const std::string& config_path, cae::Level min_level, const std::string& log_dir) {
    std::ofstream output(config_path.c_str(), std::ios::out | std::ios::trunc);
    require_true(output.is_open(), "failed to open config file for writing: " + config_path);

    const char* level = min_level == cae::Level::Debug ? "debug" : "warn";
    output << "thread_model = MT\n"
           << "process_model = SP\n"
           << "io_mode = Sync\n"
           << "truncate_file = true\n"
           << "enable_console = false\n"
           << "enable_text_log = true\n"
           << "enable_analysis_log = false\n"
           << "min_level = " << level << "\n"
           << "flush_level = error\n"
           << "log_dir = " << log_dir << "\n"
           << "analysis_log_name = cae_events.jsonl\n"
           << "global_pattern = %v\n"
           << "logger_health_interval_events = 0\n";
}

cae::LoggerOptions make_base_options(const std::string& log_dir, cae::Level min_level) {
    cae::LoggerOptions options;
    options.thread_model = cae::ThreadModel::MultiThread;
    options.process_model = cae::ProcessModel::SingleProcess;
    options.io_mode = cae::IOMode::Sync;
    options.enable_console = false;
    options.enable_text_log = true;
    options.enable_analysis_log = false;
    options.truncate_file = true;
    options.min_level = min_level;
    options.flush_level = cae::Level::Error;
    options.log_dir = log_dir;
    options.global_pattern = "%v";
    options.logger_health_interval_events = 0;
    return options;
}

void test_load_options_then_modify_before_init(const std::string& base_dir) {
    const std::string original_dir = join_path(base_dir, "load_original");
    const std::string modified_dir = join_path(base_dir, "load_modified");
    make_directory(original_dir);
    make_directory(modified_dir);

    const std::string config_path = join_path(base_dir, "load_options.ini");
    write_config(config_path, cae::Level::Warn, original_dir);

    cae::LoggerOptions options = cae::load_options_from_file(config_path);
    require_true(options.min_level == cae::Level::Warn, "loaded min_level should come from ini");

    options.min_level = cae::Level::Debug;
    options.log_dir = modified_dir;
    cae::init(options);

    const cae::LoggerOptions snapshot = cae::get_options();
    require_true(snapshot.min_level == cae::Level::Debug, "get_options should expose updated min_level");
    require_true(snapshot.log_dir == modified_dir, "get_options should expose updated log_dir");

    CAE_LOG(Debug).module("LoadOptions")
        .message("load_options_modified_debug_visible")
        .submit();
    cae::shutdown();

    require_true(file_contains(text_log_path(modified_dir, "LoadOptions"),
                               "load_options_modified_debug_visible"),
                 "modified options should route debug log to modified directory");
    require_true(!file_contains(text_log_path(original_dir, "LoadOptions"),
                                "load_options_modified_debug_visible"),
                 "modified options should not write to original config directory");
}

void test_update_options_reconfigures_level_and_log_dir(const std::string& base_dir) {
    const std::string dir_a = join_path(base_dir, "runtime_a");
    const std::string dir_b = join_path(base_dir, "runtime_b");
    make_directory(dir_a);
    make_directory(dir_b);

    cae::init(make_base_options(dir_a, cae::Level::Warn));

    CAE_LOG(Debug).module("RuntimeUpdate")
        .message("runtime_debug_filtered_before_update")
        .submit();
    CAE_LOG(Error).module("RuntimeUpdate")
        .message("runtime_error_visible_before_update")
        .submit();

    cae::LoggerOptions options = cae::get_options();
    require_true(options.min_level == cae::Level::Warn, "snapshot should reflect initial warn level");
    options.min_level = cae::Level::Debug;
    options.log_dir = dir_b;
    cae::update_options(options);

    const cae::LoggerOptions updated = cae::get_options();
    require_true(updated.min_level == cae::Level::Debug, "updated snapshot should reflect debug level");
    require_true(updated.log_dir == dir_b, "updated snapshot should reflect new log directory");

    CAE_LOG(Debug).module("RuntimeUpdate")
        .message("runtime_debug_visible_after_update")
        .submit();
    CAE_LOG(Info).module("RuntimeUpdate")
        .message("runtime_info_visible_after_update")
        .submit();
    cae::shutdown();

    const std::string log_a = text_log_path(dir_a, "RuntimeUpdate");
    const std::string log_b = text_log_path(dir_b, "RuntimeUpdate");
    require_true(file_contains(log_a, "runtime_error_visible_before_update"),
                 "old directory should contain pre-update error");
    require_true(!file_contains(log_a, "runtime_debug_visible_after_update"),
                 "old directory should not receive post-update debug");
    require_true(file_contains(log_b, "runtime_debug_visible_after_update"),
                 "new directory should receive post-update debug");
    require_true(file_contains(log_b, "runtime_info_visible_after_update"),
                 "new directory should receive post-update info");
}

void test_config_path_reload_applies_full_options(const std::string& base_dir) {
    const std::string dir_a = join_path(base_dir, "reload_a");
    const std::string dir_b = join_path(base_dir, "reload_b");
    make_directory(dir_a);
    make_directory(dir_b);

    const std::string config_path = join_path(base_dir, "runtime_reload.ini");
    write_config(config_path, cae::Level::Warn, dir_a);
    cae::init(config_path);

    CAE_LOG(Debug).module("ConfigReload")
        .message("config_reload_debug_filtered_before")
        .submit();
    CAE_LOG(Error).module("ConfigReload")
        .message("config_reload_error_visible_before")
        .submit();

    sleep_milliseconds(1200);
    write_config(config_path, cae::Level::Debug, dir_b);
    sleep_milliseconds(1200);

    CAE_LOG(Debug).module("ConfigReload")
        .message("config_reload_debug_visible_after")
        .submit();
    cae::shutdown();

    const std::string log_a = text_log_path(dir_a, "ConfigReload");
    const std::string log_b = text_log_path(dir_b, "ConfigReload");
    require_true(file_contains(log_a, "config_reload_error_visible_before"),
                 "config reload old directory should contain pre-reload error");
    require_true(!file_contains(log_a, "config_reload_debug_visible_after"),
                 "config reload old directory should not receive post-reload debug");
    require_true(file_contains(log_b, "config_reload_debug_visible_after"),
                 "config reload new directory should receive post-reload debug");
}

} // namespace

int main() {
    const std::string base_dir = std::string("runtime_config_update_out_")
                               + std::to_string(static_cast<long long>(std::time(nullptr)));
    make_directory(base_dir);

    try {
        test_load_options_then_modify_before_init(base_dir);
        test_update_options_reconfigures_level_and_log_dir(base_dir);
        test_config_path_reload_applies_full_options(base_dir);
    } catch (const std::exception& error) {
        cae::shutdown();
        std::cerr << error.what() << std::endl;
        return 1;
    }

    return 0;
}
