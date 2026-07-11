#include <fmt/format.h>

#include <string>

int main()
{
    const std::string aMessage = fmt::format("fmt {}", 90100);
    return aMessage == "fmt 90100" ? 0 : 1;
}
