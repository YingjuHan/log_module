# Local Conda build workflow

Run these commands from an initialized Windows PowerShell or Command Prompt.
They build the dependency recipes in the required order, then build the
`cae_logger` recipe against the locally built packages.

```bat
conda activate lvae
conda build D:\workspace\log_module\conda_test\conda.recipe\fmt
conda build D:\workspace\log_module\conda_test\conda.recipe\spdlog --use-local
conda build D:\workspace\log_module\conda_test\conda.recipe\boost
conda build D:\workspace\log_module\cae_log_module\conda.recipe --use-local
conda install -n lvae --use-local fmt=9.1.0 spdlog=1.11.0 boost=1.68.0 cae_logger=1.0.0
```

Each `conda build` command constructs and uses its own isolated build and test
prefixes. The recipes package their outputs into the local Conda channel; they
do not directly write headers, libraries, or CMake files into the `lvae`
environment. Only the final `conda install` changes `lvae`.

On Linux, follow the same `fmt`, `spdlog`, `boost`, then `cae_logger` command
order, adapting the absolute recipe paths to the local checkout location.
