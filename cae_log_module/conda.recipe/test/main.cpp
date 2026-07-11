#include "cae_logger.h"

#include <fstream>
#include <iterator>
#include <string>

int main()
{
    cae::LoggerOptions anOptions;
    anOptions.io_mode = cae::IOMode::Sync;
    anOptions.enable_console = false;
    anOptions.enable_text_log = true;
    anOptions.enable_analysis_log = false;
    anOptions.truncate_file = true;
    anOptions.log_dir = "conda-test-logs";

    cae::init(anOptions);
    CAE_LOG(Info)
        .module("CondaConsumer")
        .message("Installed cae_logger package is available.")
        .submit();
    {
        CAE_LOG_SCOPE(Info)
            .module("CondaConsumer")
            .message("Conda scope completed.")
            .submit();
    }
    cae::shutdown();

    std::ifstream aLog("conda-test-logs/CondaConsumer.log", std::ios::binary);
    const std::string aText((std::istreambuf_iterator<char>(aLog)),
                            std::istreambuf_iterator<char>());
    return aText.find("duration_us=") == std::string::npos ? 1 : 0;
}
