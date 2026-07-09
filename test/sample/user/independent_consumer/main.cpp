#include "cae_logger.h"

int main() {
    cae::LoggerOptions options;
    options.enable_console = true;
    options.enable_text_log = true;
    options.enable_analysis_log = true;
    options.log_dir = "doc_logs";
    options.analysis_log_name = "consumer_events.jsonl";
    options.min_level = cae::Level::Info;
    options.flush_level = cae::Level::Error;

    cae::init(options);
    cae::set_session("IndependentCase_001");
    cae::set_thread_name("MainThread");

    CAE_LOG(Info)
        .module("System")
        .stage("Workflow")
        .action("application_start")
        .result("started")
        .message("Independent consumer started.")
        .submit();

    cae::shutdown();
    return 0;
}
