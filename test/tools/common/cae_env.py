#!/usr/bin/env python3
"""Shared CAE tool environment helpers."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

# ── 环境变量名常量 ────────────────────────────────────────────────────
ENV_GOACCESS_EXE = "CAE_GOACCESS_EXE"            # GoAccess 可执行文件路径
ENV_GOACCESS_BUILD_DIR = "CAE_GOACCESS_BUILD_DIR"  # GoAccess 构建目录
ENV_GOACCESS_SOURCE_DIR = "CAE_GOACCESS_SOURCE_DIR"  # GoAccess 源码目录
ENV_APP_EXE = "CAE_APP_EXE"                      # sample app 可执行文件路径
ENV_APP_BUILD_DIR = "CAE_APP_BUILD_DIR"          # sample app 构建目录
ENV_CONFIG_DIR = "CAE_CONFIG_DIR"                # CAE 配置目录
ENV_PROFILE_CONFIG = "CAE_PROFILE_CONFIG"        # GoAccess 配置文件路径
ENV_LOGS_DIR = "CAE_LOGS_DIR"                    # CAE 日志目录
ENV_REPORTS_DIR = "CAE_REPORTS_DIR"              # CAE 报告输出目录
ENV_MAIN_BUILD_DIR = "CAE_MAIN_BUILD_DIR"        # cae_logger 主构建目录
ENV_MAIN_INSTALL_DIR = "CAE_MAIN_INSTALL_DIR"    # cae_logger 安装目录
ENV_CAE_LOGGER_DIR = "CAE_CAE_LOGGER_DIR"        # cae_logger 包目录

# 单配置 CMake 生成器集合（无需通过 --config 指定构建类型）
SINGLE_CONFIG_GENERATORS = {
    "Ninja",
    "Unix Makefiles",
    "MinGW Makefiles",
    "MSYS Makefiles",
}

# 用于判断生成器是否面向 Windows 的标记字符串
WINDOWS_GENERATOR_MARKERS = (
    "MinGW",
    "MSYS",
)

# 常见的多配置生成器配置名称
COMMON_MULTI_CONFIGS = (
    "Debug",
    "Release",
    "RelWithDebInfo",
    "MinSizeRel",
)

TOOLCHAIN_GENERATORS = {
    "MINGW": "MinGW Makefiles",
    "GCC": "Unix Makefiles",
}


def _binary_name(stem: str) -> str:
    """根据平台返回可执行文件全名，Windows 下追加 .exe 后缀。"""
    return f"{stem}.exe" if os.name == "nt" else stem


def resolve_path(value: str | os.PathLike[str] | Path | None, base: str | os.PathLike[str] | Path | None = None) -> Path | None:
    """Resolve a possibly relative path against a base directory."""
    if value in (None, ""):
        return None

    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        base_dir = Path(base) if base is not None else Path.cwd()
        candidate = base_dir / candidate
    return candidate.resolve(strict=False)


def merge_manifest(base: Mapping[str, Any] | None, override: Mapping[str, Any] | None) -> dict[str, Any]:
    """Recursively merge two manifest dictionaries."""
    merged = deepcopy(dict(base or {}))
    for key, value in dict(override or {}).items():
        if isinstance(merged.get(key), dict) and isinstance(value, Mapping):
            merged[key] = merge_manifest(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _serialize_manifest(value: Any) -> Any:
    """递归序列化 manifest 值，将 Path 对象转为字符串以便 JSON 输出。"""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {key: _serialize_manifest(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_manifest(item) for item in value]
    return value


def load_manifest(path: str | os.PathLike[str] | Path | None) -> dict[str, Any]:
    """Load a CAE manifest JSON file. Missing manifests resolve to an empty dict."""
    manifest_path = resolve_path(path)
    if manifest_path is None or not manifest_path.exists():
        return {}

    with manifest_path.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest root must be a JSON object: {manifest_path}")
    return payload


def write_manifest(path: str | os.PathLike[str] | Path, manifest: Mapping[str, Any]) -> Path:
    """Write a CAE manifest JSON file."""
    manifest_path = resolve_path(path)
    if manifest_path is None:
        raise ValueError("Manifest path must not be empty")

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as fh:
        json.dump(_serialize_manifest(dict(manifest)), fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    return manifest_path


def check_file(path: str | os.PathLike[str] | Path, label: str = "File") -> Path:
    """Ensure a file exists."""
    candidate = resolve_path(path)
    if candidate is None or not candidate.is_file():
        raise FileNotFoundError(f"{label} not found: {candidate}")
    return candidate


def check_dir(path: str | os.PathLike[str] | Path, label: str = "Directory") -> Path:
    """Ensure a directory exists."""
    candidate = resolve_path(path)
    if candidate is None or not candidate.is_dir():
        raise FileNotFoundError(f"{label} not found: {candidate}")
    return candidate


def run_checked(
    cmd: Sequence[str | os.PathLike[str]],
    cwd: str | os.PathLike[str] | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: int = 300,
) -> subprocess.CompletedProcess[bytes]:
    """Run a command and raise a clear error on failure."""
    cmd_list = [str(part) for part in cmd]
    cwd_path = resolve_path(cwd) if cwd is not None else None
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)

    try:
        result = subprocess.run(
            cmd_list,
            cwd=str(cwd_path) if cwd_path is not None else None,
            env=merged_env,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        rendered = " ".join(shlex.quote(part) for part in cmd_list)
        raise RuntimeError(f"Command timed out after {timeout}s: {rendered}") from exc

    if result.returncode != 0:
        rendered = " ".join(shlex.quote(part) for part in cmd_list)
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {rendered}")
    return result


@lru_cache(maxsize=1)
def default_cmake_generator() -> str | None:
    """Return CMake's default generator as reported by cmake --help."""
    try:
        result = subprocess.run(
            ["cmake", "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("* "):
            return stripped[2:].split("=", 1)[0].strip()
    return None


def normalize_toolchain(value: str | None) -> str | None:
    """Normalize a supported compiler/toolchain category."""
    if value in (None, ""):
        return None
    normalized = value.upper()
    if normalized not in TOOLCHAIN_GENERATORS:
        supported = ", ".join(sorted(TOOLCHAIN_GENERATORS))
        raise ValueError(f"Unsupported toolchain '{value}'; expected one of: {supported}")
    return normalized


def generator_for_toolchain(toolchain: str | None) -> str | None:
    """Return the CMake generator associated with a toolchain category."""
    normalized = normalize_toolchain(toolchain)
    if normalized is None:
        return None
    return TOOLCHAIN_GENERATORS[normalized]


def resolve_cmake_generator_choice(generator: str | None, toolchain: str | None) -> str | None:
    """Prefer an explicit generator, otherwise resolve one from a toolchain category."""
    if generator not in (None, ""):
        return generator
    return generator_for_toolchain(toolchain)


def effective_cmake_generator(generator: str | None) -> str | None:
    """Return the explicit, environment-provided, or default CMake generator."""
    return generator or os.environ.get("CMAKE_GENERATOR") or default_cmake_generator()


def cmake_cache_value(build_dir: str | os.PathLike[str] | Path, key: str) -> str | None:
    """Read a CMake cache value from an existing build directory."""
    resolved_build_dir = resolve_path(build_dir)
    if resolved_build_dir is None:
        return None
    cache_path = resolved_build_dir / "CMakeCache.txt"
    if not cache_path.is_file():
        return None

    prefix = f"{key}:"
    try:
        with cache_path.open(encoding="utf-8", errors="replace") as fh:
            for raw_line in fh:
                line = raw_line.rstrip("\n")
                if line.startswith(prefix):
                    _, _, value = line.partition("=")
                    return value
    except OSError:
        return None
    return None


def cached_cmake_generator(build_dir: str | os.PathLike[str] | Path) -> str | None:
    """Return the generator recorded in an existing CMake build directory."""
    return cmake_cache_value(build_dir, "CMAKE_GENERATOR")


def cmake_build_dir_needs_fresh_configure(
    build_dir: str | os.PathLike[str] | Path,
    generator: str | None,
) -> bool:
    """Return whether an existing CMake build dir uses a different generator."""
    cached_generator = cached_cmake_generator(build_dir)
    effective_generator = effective_cmake_generator(generator)
    return bool(cached_generator and effective_generator and cached_generator != effective_generator)


def _is_multi_config_generator_name(generator: str) -> bool:
    """Return whether a concrete CMake generator is multi-config."""
    if generator in SINGLE_CONFIG_GENERATORS:
        return False
    return (
        "Multi-Config" in generator
        or generator == "Xcode"
    )


def generator_targets_windows(generator: str | None) -> bool:
    """Return whether a generator normally targets Windows."""
    if os.name == "nt":
        return True
    effective_generator = effective_cmake_generator(generator)
    if not effective_generator:
        return False
    return any(marker in effective_generator for marker in WINDOWS_GENERATOR_MARKERS)


def is_multi_config_generator(generator: str | None) -> bool:
    """Return whether CMake build/install commands should receive --config."""
    effective_generator = effective_cmake_generator(generator)
    if effective_generator is None:
        return False
    return _is_multi_config_generator_name(effective_generator)


def is_multi_config_build_dir(
    build_dir: str | os.PathLike[str] | Path,
    generator: str | None,
) -> bool:
    """Return whether an existing or future CMake build dir is multi-config."""
    cached_generator = cached_cmake_generator(build_dir)
    effective_generator = effective_cmake_generator(generator)
    if cached_generator and effective_generator and cached_generator != effective_generator:
        return _is_multi_config_generator_name(effective_generator)

    configuration_types = cmake_cache_value(build_dir, "CMAKE_CONFIGURATION_TYPES")
    if configuration_types is not None:
        return bool(configuration_types.strip())

    if cached_generator:
        return _is_multi_config_generator_name(cached_generator)

    return is_multi_config_generator(generator)


def should_pass_config(generator: str | None, config: str | None) -> bool:
    """Return whether build/install commands should include --config."""
    return bool(config and is_multi_config_generator(generator))


def should_pass_config_for_build_dir(
    build_dir: str | os.PathLike[str] | Path,
    generator: str | None,
    config: str | None,
) -> bool:
    """Return whether build/install commands should include --config for a build dir."""
    return bool(config and is_multi_config_build_dir(build_dir, generator))


def merge_build_type_option(
    cmake_options: Sequence[tuple[str, str]],
    generator: str | None,
    config: str | None,
) -> list[tuple[str, str]]:
    """Add CMAKE_BUILD_TYPE for single-config generators unless explicitly set."""
    merged = list(cmake_options)
    if not config or is_multi_config_generator(generator):
        return merged
    if any(key == "CMAKE_BUILD_TYPE" for key, _ in merged):
        return merged
    merged.append(("CMAKE_BUILD_TYPE", config))
    return merged


def merge_build_type_option_for_build_dir(
    cmake_options: Sequence[tuple[str, str]],
    build_dir: str | os.PathLike[str] | Path,
    generator: str | None,
    config: str | None,
) -> list[tuple[str, str]]:
    """Add CMAKE_BUILD_TYPE using the build dir cache when present."""
    merged = list(cmake_options)
    if not config or is_multi_config_build_dir(build_dir, generator):
        return merged
    if any(key == "CMAKE_BUILD_TYPE" for key, _ in merged):
        return merged
    merged.append(("CMAKE_BUILD_TYPE", config))
    return merged


def cmake_configure_command(
    *,
    source_dir: Path,
    build_dir: Path,
    generator: str | None,
    fresh: bool = False,
) -> list[str]:
    """Build the common CMake configure command prefix."""
    cmd = ["cmake"]
    if fresh:
        cmd.append("--fresh")

    command_generator = generator
    if fresh and command_generator is None:
        command_generator = effective_cmake_generator(None)
    if command_generator:
        cmd.extend(["-G", command_generator])
    cmd.extend(["-S", str(source_dir), "-B", str(build_dir)])
    return cmd


def default_binary_dir(build_dir: Path, stem: str) -> Path:
    """Infer the most likely runtime directory for a built binary."""
    binary_name = _binary_name(stem)
    # 先直接检查构建根目录
    root_binary = build_dir / binary_name
    if root_binary.is_file():
        return build_dir.resolve(strict=False)

    # 检查环境变量指定的构建类型子目录
    requested_config = os.environ.get("CMAKE_BUILD_TYPE")
    if requested_config:
        config_binary = build_dir / requested_config / binary_name
        if config_binary.is_file():
            return config_binary.parent.resolve(strict=False)

    # 遍历常见多配置名称寻找二进制文件
    for config_name in COMMON_MULTI_CONFIGS:
        config_binary = build_dir / config_name / binary_name
        if config_binary.is_file():
            return config_binary.parent.resolve(strict=False)

    if is_multi_config_generator(None):
        return (build_dir / "Debug").resolve(strict=False)
    return build_dir.resolve(strict=False)


def _manifest_lookup(manifest: Mapping[str, Any], keys: Sequence[str]) -> Any:
    """按 keys 路径从嵌套的 manifest 字典中递归取值，未找到返回 None。"""
    current: Any = manifest
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def default_spdlog_package_dir(repo_root: str | os.PathLike[str] | Path) -> Path | None:
    """Return no implicit spdlog package path; callers must configure spdlog explicitly."""
    del repo_root
    return None


@dataclass(frozen=True)
class RepoPaths:
    """Repository-relative default paths for CAE tooling."""

    repo_root: Path          # 仓库根目录
    tools_dir: Path          # tools 脚本目录
    build_dir: Path          # 总构建目录
    main_build_dir: Path     # cae_logger 主库构建目录
    main_install_dir: Path   # cae_logger 安装目录
    sample_source_dir: Path  # sample 示例工程源码目录
    app_build_dir: Path      # sample 构建目录
    app_config_dir: Path     # sample 运行时目录（二进制所在目录）
    cae_logger_package_dir: Path  # cae_logger CMake 包目录
    config_dir: Path         # CAE 配置文件目录
    logs_dir: Path           # CAE 日志输出目录
    reports_dir: Path        # CAE 报告输出目录
    goaccess_source_dir: Path  # GoAccess 源码目录
    goaccess_build_dir: Path   # GoAccess 构建目录
    profile_config: Path     # GoAccess 配置文件路径
    app_exe: Path            # sample 可执行文件路径
    goaccess_exe: Path       # GoAccess 可执行文件路径
    manifest_path: Path      # manifest JSON 文件路径

    @classmethod
    def from_repo_root(cls, repo_root: str | os.PathLike[str] | Path) -> "RepoPaths":
        """从仓库根目录初始化所有路径。"""
        root = resolve_path(repo_root)
        if root is None:
            raise ValueError("repo_root must not be empty")

        workspace_root = root.parent
        tools_dir = root / "tools"
        build_dir = root / "build"
        main_build_dir = workspace_root / "cae_log_module" / "build" / "Debug"
        main_install_dir = workspace_root / "cae_log_module" / "install" / "Debug"
        sample_source_dir = root
        app_build_dir = build_dir
        app_config_dir = default_binary_dir(app_build_dir, "app_main")
        cae_logger_package_dir = main_install_dir / "lib" / "cmake" / "cae_logger"
        config_dir = root / "config"
        out_dir = root / "out"
        logs_dir = out_dir / "logs"
        reports_dir = out_dir / "reports"
        goaccess_source_dir = workspace_root / "goaccess"
        goaccess_build_dir = goaccess_source_dir / "build" / "Debug"
        profile_config = config_dir / "cae_goaccess.conf"
        app_exe = app_config_dir / _binary_name("app_main")
        goaccess_exe = default_binary_dir(goaccess_build_dir, "goaccess") / _binary_name("goaccess")
        manifest_path = out_dir / "cae_manifest.json"

        return cls(
            repo_root=root,
            tools_dir=tools_dir,
            build_dir=build_dir,
            main_build_dir=main_build_dir,
            main_install_dir=main_install_dir,
            sample_source_dir=sample_source_dir,
            app_build_dir=app_build_dir,
            app_config_dir=app_config_dir,
            cae_logger_package_dir=cae_logger_package_dir,
            config_dir=config_dir,
            logs_dir=logs_dir,
            reports_dir=reports_dir,
            goaccess_source_dir=goaccess_source_dir,
            goaccess_build_dir=goaccess_build_dir,
            profile_config=profile_config,
            app_exe=app_exe,
            goaccess_exe=goaccess_exe,
            manifest_path=manifest_path,
        )

    @classmethod
    def discover(cls, anchor: str | os.PathLike[str] | Path | None = None) -> "RepoPaths":
        """自动发现仓库根目录（默认基于本文件位置上溯两级），构造路径集合。"""
        anchor_path = Path(anchor).resolve() if anchor is not None else Path(__file__).resolve()
        current = anchor_path.parent if anchor_path.is_file() else anchor_path

        for candidate in (current, *current.parents):
            if (
                (candidate / "tools").is_dir()
                and (candidate / "sample").is_dir()
                and (candidate / "config").is_dir()
                and (candidate / "CMakeLists.txt").is_file()
            ):
                return cls.from_repo_root(candidate)

        raise FileNotFoundError(f"Failed to discover repository root from anchor: {anchor_path}")


@dataclass(frozen=True)
class CaeContext:
    """Manifest, environment, and default path resolution context."""

    repo_paths: RepoPaths                 # 仓库路径集合
    manifest: dict[str, Any]              # 合并后的 manifest 配置
    environ: Mapping[str, str]             # 当前环境变量快照
    manifest_path: Path                   # manifest 文件路径

    @classmethod
    def create(
        cls,
        repo_paths: RepoPaths | None = None,
        manifest_path: str | os.PathLike[str] | Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> "CaeContext":
        """工厂方法：创建 CaeContext，自动发现路径、加载 manifest 并获取环境变量。"""
        repo = repo_paths or RepoPaths.discover()
        manifest_file = resolve_path(manifest_path or repo.manifest_path, repo.repo_root)
        if manifest_file is None:
            raise ValueError("manifest_path must not be empty")
        return cls(
            repo_paths=repo,
            manifest=load_manifest(manifest_file),
            environ=dict(environ or os.environ),
            manifest_path=manifest_file,
        )

    def pick(
        self,
        *,
        cli_value: Any = None,
        env_var: str | None = None,
        manifest_keys: Sequence[str] = (),
        default: Any = None,
    ) -> Any:
        """按 CLI > 环境变量 > manifest > 默认值的优先级选择一个值。"""
        if cli_value not in (None, ""):
            return cli_value

        if env_var:
            env_value = self.environ.get(env_var)
            if env_value not in (None, ""):
                return env_value

        manifest_value = _manifest_lookup(self.manifest, manifest_keys)
        if manifest_value not in (None, ""):
            return manifest_value

        return default

    def path_value(
        self,
        *,
        cli_value: str | os.PathLike[str] | Path | None = None,
        env_var: str | None = None,
        manifest_keys: Sequence[str] = (),
        default: str | os.PathLike[str] | Path | None = None,
        base: str | os.PathLike[str] | Path | None = None,
    ) -> Path | None:
        """按优先级解析路径值，并相对于仓库根目录做路径解析。"""
        chosen = self.pick(
            cli_value=cli_value,
            env_var=env_var,
            manifest_keys=manifest_keys,
            default=default,
        )
        return resolve_path(chosen, base or self.repo_paths.repo_root)


# ── 模块公开 API ──────────────────────────────────────────────────────
__all__ = [
    "ENV_APP_BUILD_DIR",
    "ENV_APP_EXE",
    "ENV_CAE_LOGGER_DIR",
    "ENV_CONFIG_DIR",
    "ENV_GOACCESS_BUILD_DIR",
    "ENV_GOACCESS_EXE",
    "ENV_GOACCESS_SOURCE_DIR",
    "ENV_LOGS_DIR",
    "ENV_MAIN_BUILD_DIR",
    "ENV_MAIN_INSTALL_DIR",
    "ENV_PROFILE_CONFIG",
    "ENV_REPORTS_DIR",
    "CaeContext",
    "RepoPaths",
    "TOOLCHAIN_GENERATORS",
    "cached_cmake_generator",
    "check_dir",
    "check_file",
    "cmake_build_dir_needs_fresh_configure",
    "cmake_cache_value",
    "default_cmake_generator",
    "default_spdlog_package_dir",
    "generator_for_toolchain",
    "is_multi_config_build_dir",
    "is_multi_config_generator",
    "load_manifest",
    "merge_build_type_option",
    "merge_build_type_option_for_build_dir",
    "merge_manifest",
    "normalize_toolchain",
    "resolve_cmake_generator_choice",
    "resolve_path",
    "run_checked",
    "should_pass_config",
    "should_pass_config_for_build_dir",
    "write_manifest",
]
