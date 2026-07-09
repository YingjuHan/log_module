#define emit

#include "cae_logger.h"

int main()
{
    cae::LoggerOptions anOptions;
    anOptions.enable_console = false;
    anOptions.enable_text_log = false;
    anOptions.enable_analysis_log = false;
    anOptions.min_level = cae::Level::Info;

    cae::init(anOptions);
    CAE_LOG(Info)
        .module("Qt")
        .stage("Compatibility")
        .action("emit_macro")
        .message("Qt emit macro compatibility check.")
        .submit();
    CAE_LOG_INFO("Qt")
        .stage("Compatibility")
        .action("chain_macro")
        .message("Qt emit macro chain compatibility check.")
        .submit();
    CAE_LOG_INFO_DUR("Qt", 12)
        .stage("Compatibility")
        .action("chain_duration_macro")
        .message("Qt emit macro duration chain compatibility check.")
        .submit();
    cae::shutdown();

    return 0;
}
