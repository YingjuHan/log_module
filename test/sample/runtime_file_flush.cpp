#include "cae_logger.h"

#include <cstdlib>
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

bool file_contains(const std::string& path, const std::string& needle) {
    std::ifstream input(path.c_str(), std::ios::binary);
    if (!input.is_open()) {
        return false;
    }

    const std::string content((std::istreambuf_iterator<char>(input)),
                              std::istreambuf_iterator<char>());
    return content.find(needle) != std::string::npos;
}

std::string quote_argument(const std::string& value) {
    std::string quoted = "\"";
    for (std::string::const_iterator it = value.begin(); it != value.end(); ++it) {
        if (*it == '"') {
            quoted += "\\\"";
        } else {
            quoted += *it;
        }
    }
    quoted += "\"";
    return quoted;
}

#ifdef _WIN32
std::string absolute_path(const std::string& path) {
    char buffer[MAX_PATH];
    const DWORD length = GetFullPathNameA(path.c_str(), MAX_PATH, buffer, NULL);
    if (length == 0 || length >= MAX_PATH) {
        return path;
    }

    return std::string(buffer, length);
}
#endif

bool run_child_process(const std::string& executable, const std::string& log_dir) {
#ifdef _WIN32
    const std::string application = absolute_path(executable);
    std::string       command = quote_argument(application) + " --child " + quote_argument(log_dir);

    STARTUPINFOA        startup_info;
    PROCESS_INFORMATION process_info;
    ZeroMemory(&startup_info, sizeof(startup_info));
    ZeroMemory(&process_info, sizeof(process_info));
    startup_info.cb = sizeof(startup_info);

    const BOOL created = CreateProcessA(application.c_str(),
                                        &command[0],
                                        NULL,
                                        NULL,
                                        FALSE,
                                        0,
                                        NULL,
                                        NULL,
                                        &startup_info,
                                        &process_info);
    if (!created) {
        std::cerr << "CreateProcessA failed: " << GetLastError() << std::endl;
        return false;
    }

    WaitForSingleObject(process_info.hProcess, INFINITE);
    DWORD exit_code = 0;
    GetExitCodeProcess(process_info.hProcess, &exit_code);
    CloseHandle(process_info.hThread);
    CloseHandle(process_info.hProcess);
    return exit_code == 23;
#else
    const std::string command = quote_argument(executable) + " --child " + quote_argument(log_dir);
    return std::system(command.c_str()) != -1;
#endif
}

void terminate_without_shutdown(int exit_code) {
#ifdef _WIN32
    TerminateProcess(GetCurrentProcess(), static_cast<UINT>(exit_code));
#else
    std::_Exit(exit_code);
#endif
    std::abort();
}

std::string text_log_path(const std::string& log_dir, const std::string& module) {
    return join_path(log_dir, module + ".log");
}

std::string analysis_log_path(const std::string& log_dir) {
    return join_path(log_dir, "cae_events.jsonl");
}

cae::LoggerOptions make_options(const std::string& log_dir, cae::IOMode io_mode) {
    cae::LoggerOptions options;
    options.thread_model = cae::ThreadModel::MultiThread;
    options.process_model = cae::ProcessModel::SingleProcess;
    options.io_mode = io_mode;
    options.enable_console = false;
    options.enable_text_log = true;
    options.enable_analysis_log = true;
    options.truncate_file = true;
    options.min_level = cae::Level::Trace;
    options.flush_level = cae::Level::Error;
    options.log_dir = log_dir;
    options.analysis_log_name = "cae_events.jsonl";
    options.global_pattern = "%v";
    options.logger_health_interval_events = 0;
    options.enable_call_chain_analysis = false;
    return options;
}

void emit_info_record(const std::string& message) {
    CAE_LOG(Info).module("ImmediateFlush")
        .event_type(cae::EventType::System)
        .stage("Runtime")
        .action("flush")
        .message("{}", message)
        .submit();
}

void test_file_outputs_are_readable_before_shutdown(const std::string& base_dir) {
    const std::string log_dir = join_path(base_dir, "before_shutdown");
    const std::string message = "info_visible_before_shutdown";
    make_directory(log_dir);

    cae::init(make_options(log_dir, cae::IOMode::Sync));
    emit_info_record(message);

    require_true(file_contains(text_log_path(log_dir, "ImmediateFlush"), message),
                 "text log should be readable immediately after an info record");
    require_true(file_contains(analysis_log_path(log_dir), message),
                 "analysis log should be readable immediately after an info record");

    cae::shutdown();
}

void run_child_without_shutdown(const std::string& log_dir) {
    make_directory(log_dir);
    cae::init(make_options(log_dir, cae::IOMode::Async));
    emit_info_record("child_info_visible_after_forced_exit");
    terminate_without_shutdown(23);
}

void test_async_child_forced_exit_keeps_last_file_record(const std::string& executable,
                                                        const std::string& base_dir) {
    const std::string log_dir = join_path(base_dir, "forced_exit");
    make_directory(log_dir);

    require_true(run_child_process(executable, log_dir), "failed to start forced-exit child process");

    require_true(file_contains(text_log_path(log_dir, "ImmediateFlush"),
                               "child_info_visible_after_forced_exit"),
                 "text log should contain the child info record after forced exit");
    require_true(file_contains(analysis_log_path(log_dir),
                               "child_info_visible_after_forced_exit"),
                 "analysis log should contain the child info record after forced exit");
}

} // namespace

int main(int argc, char** argv) {
    if (argc == 3 && std::string(argv[1]) == "--child") {
        run_child_without_shutdown(argv[2]);
    }

    const std::string base_dir = std::string("runtime_file_flush_out_")
                               + std::to_string(static_cast<long long>(std::time(nullptr)));
    make_directory(base_dir);

    try {
        test_file_outputs_are_readable_before_shutdown(base_dir);
        test_async_child_forced_exit_keeps_last_file_record(argv[0], base_dir);
    } catch (const std::exception& error) {
        cae::shutdown();
        std::cerr << error.what() << std::endl;
        return 1;
    }

    return 0;
}
