#include "cae_logger.h"

void scope_must_be_submitted()
{
    CAE_LOG_SCOPE(Info)
        .module("CompileContract")
        .message("This scoped timer intentionally omits submit.");
}
