#include <fmt/format.h>
#include <spdlog/spdlog.h>

#include <string>

int main()
{
    const std::string aMessage = fmt::format("external fmt {}", 90100);
    spdlog::info("{}", aMessage);
    return aMessage == "external fmt 90100" ? 0 : 1;
}
