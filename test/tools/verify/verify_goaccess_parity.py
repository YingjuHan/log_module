#!/usr/bin/env python3
"""Generate and compare GoAccess autotools/CMake config headers."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
from typing import Dict, Iterable, List, Tuple


DEFINE_RE = re.compile(r"^#define\s+([A-Za-z0-9_]+)(?:\s+(.*?))?\s*$")
UNDEF_RE = re.compile(r"^/\*\s+#undef\s+([A-Za-z0-9_]+)\s+\*/\s*$")

EXCEPTION_REASONS = {
    "HAVE_CURSES_H": "PDCurses backend differs from autotools ncurses header layout.",
    "HAVE_LIBCURSES": "PDCurses backend differs from autotools ncurses/curses library probing.",
    "HAVE_LIBNCURSES": "PDCurses backend differs from autotools ncurses library probing.",
    "HAVE_LIBNCURSESW": "PDCurses wide-character backend stands in for autotools ncursesw.",
    "HAVE_NCURSES_H": "PDCurses backend differs from autotools ncurses header layout.",
    "HAVE_NCURSES_NCURSES_H": "PDCurses backend differs from autotools ncurses header layout.",
    "HAVE_NCURSESW_NCURSES_H": "PDCurses backend differs from autotools ncursesw header layout.",
    "HAVE_ARPA_INET_H": "Windows build uses src/win compatibility headers.",
    "HAVE_GETHOSTBYADDR": "Windows build uses Winsock-backed compatibility shims.",
    "HAVE_GETHOSTBYNAME": "Windows build uses Winsock-backed compatibility shims.",
    "HAVE_NETDB_H": "Windows build uses src/win compatibility headers.",
    "HAVE_NETINET_IN_H": "Windows build uses src/win compatibility headers.",
    "HAVE_POLL": "Windows build uses src/win/poll.h to emulate poll().",
    "HAVE_REGCOMP": "Windows build uses bundled regex compatibility implementation.",
    "HAVE_SOCKET": "Windows build uses Winsock-backed compatibility shims.",
    "HAVE_SYS_SOCKET_H": "Windows build uses src/win compatibility headers.",
    "HAVE_TIMEGM": "Windows build maps timegm() to _mkgmtime.",
}


def parse_config_macros(path: str) -> Dict[str, str]:
    """Parse config.h-style macro definitions."""
    macros: Dict[str, str] = {}
    with open(path, encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            match = DEFINE_RE.match(line)
            if match:
                macros[match.group(1)] = (match.group(2) or "1").strip()
                continue
            match = UNDEF_RE.match(line)
            if match:
                macros[match.group(1)] = "UNDEF"
    return macros


def is_tracked_macro(name: str) -> bool:
    """Return whether a macro participates in parity comparison."""
    if name.startswith(("HAVE_", "ENABLE_", "WITH_")):
        return True
    return name in {"LSTAT_FOLLOWS_SLASHED_SYMLINK", "_DEBUG", "_LARGEFILE_SOURCE"}


def normalize_macro_value(value: str | None) -> str:
    """Normalize CMake/autotools boolean macro values."""
    if value is None:
        return "UNDEF"
    compact = value.strip()
    if compact in {"TRUE", "ON"}:
        return "1"
    if compact in {"FALSE", "OFF"}:
        return "UNDEF"
    return compact


def format_macro(macros: Dict[str, str], name: str) -> str:
    """Return a normalized macro value."""
    return normalize_macro_value(macros.get(name, "UNDEF"))


def windows_to_cygwin_path(path: str) -> str:
    """Convert a Windows path to Cygwin form when needed."""
    absolute = os.path.abspath(path)
    drive, tail = os.path.splitdrive(absolute)
    if not drive:
        return absolute.replace("\\", "/")
    return f"/cygdrive/{drive[0].lower()}{tail.replace('\\', '/')}"


def parse_cmake_cache(path: str) -> Dict[str, str]:
    """Parse a CMakeCache.txt into key/value pairs."""
    values: Dict[str, str] = {}
    with open(path, encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith(("//", "#")):
                continue
            if "=" not in line or ":" not in line:
                continue
            key_and_type, value = line.split("=", 1)
            key, _type = key_and_type.split(":", 1)
            values[key] = value
    return values


def truthy_cache_value(value: str | None) -> bool:
    """Return whether a CMake cache value is truthy."""
    if value is None:
        return False
    return value.upper() in {"1", "ON", "TRUE", "YES", "Y"}


def infer_configure_args(cmake_cache: Dict[str, str]) -> List[str]:
    """Infer autotools configure arguments from CMake cache values."""
    args: List[str] = []
    if truthy_cache_value(cmake_cache.get("ENABLE_NLS")):
        args.append("--enable-nls")
    if truthy_cache_value(cmake_cache.get("WITH_ZLIB")):
        args.append("--with-zlib")
    if truthy_cache_value(cmake_cache.get("WITH_GETLINE")):
        args.append("--with-getline=yes")
    if truthy_cache_value(cmake_cache.get("WITH_SSL")):
        args.append("--with-openssl=yes")
    if truthy_cache_value(cmake_cache.get("ENABLE_DEBUG")):
        args.append("--enable-debug=yes")
    if truthy_cache_value(cmake_cache.get("ENABLE_UTF8")) or truthy_cache_value(cmake_cache.get("PDCurses_WIDE")):
        args.append("--enable-utf8=yes")

    geoip_value = cmake_cache.get("ENABLE_GEOIP", "")
    if geoip_value in {"legacy", "mmdb"}:
        args.append(f"--enable-geoip={geoip_value}")
    return args


def nls_disabled_exceptions(cmake_cache: Dict[str, str]) -> Dict[str, str]:
    """Return expected parity exceptions when the CMake build disables NLS."""
    if truthy_cache_value(cmake_cache.get("ENABLE_NLS")):
        return {}
    return {
        "ENABLE_NLS": "CMake build explicitly disables Native Language Support.",
        "HAVE_DCGETTEXT": "CMake build explicitly disables Native Language Support.",
        "HAVE_GETTEXT": "CMake build explicitly disables Native Language Support.",
        "HAVE_ICONV": "CMake build explicitly disables Native Language Support.",
        "HAVE_LIBINTL": "CMake build explicitly disables Native Language Support.",
    }


def stage_source_tree(source_dir: str, staged_dir: str, build_dir: str) -> str:
    """Copy a clean GoAccess source snapshot for autotools configure."""
    source_dir = os.path.abspath(source_dir)
    build_dir = os.path.abspath(build_dir)
    staged_dir = os.path.abspath(staged_dir)

    if os.path.isdir(staged_dir):
        shutil.rmtree(staged_dir)

    root_build_dirs = {
        name
        for name in os.listdir(source_dir)
        if os.path.isdir(os.path.join(source_dir, name)) and name.startswith("build")
    }
    if os.path.commonpath([source_dir, build_dir]) == source_dir:
        root_build_dirs.add(os.path.basename(build_dir))

    def ignore(path: str, names: List[str]) -> List[str]:
        ignored: List[str] = []
        rel_path = os.path.relpath(path, source_dir)
        if rel_path == ".":
            for name in names:
                if name in {".git", "config.cache", "config.log", "config.status", "Makefile"}:
                    ignored.append(name)
                if name in root_build_dirs:
                    ignored.append(name)
        return ignored

    shutil.copytree(source_dir, staged_dir, ignore=ignore)
    return staged_dir


def run_reference_configure(
    bash_exe: str,
    source_dir: str,
    build_dir: str,
    configure_args: Iterable[str],
) -> Tuple[str, List[str], List[str]]:
    """Run autotools configure and return the generated config path."""
    source_dir = os.path.abspath(source_dir)
    build_dir = os.path.abspath(build_dir)
    os.makedirs(build_dir, exist_ok=True)
    stdout_path = os.path.join(build_dir, "configure.stdout.txt")
    stderr_path = os.path.join(build_dir, "configure.stderr.txt")
    notes: List[str] = []
    logs = [stdout_path, stderr_path]
    staged_source_dir = source_dir

    if os.path.exists(os.path.join(source_dir, "config.status")) or os.path.exists(os.path.join(source_dir, "Makefile")):
        staged_source_dir = stage_source_tree(
            source_dir,
            os.path.join(build_dir, "_source_snapshot"),
            build_dir,
        )
        notes.append("Reference configure used a staged source snapshot.")

    cygwin_source = windows_to_cygwin_path(staged_source_dir)
    cygwin_build = windows_to_cygwin_path(build_dir)
    env = os.environ.copy()
    resolved_bash = shutil.which(bash_exe) if not os.path.isabs(bash_exe) else bash_exe
    if not resolved_bash or not os.path.isfile(resolved_bash):
        raise FileNotFoundError(
            "Unable to locate the requested bash executable. Install Cygwin bash on PATH "
            "or pass --cygwin-bash explicitly."
        )
    env["PATH"] = os.path.dirname(os.path.abspath(resolved_bash)) + os.pathsep + env.get("PATH", "")

    def run_once(args: Iterable[str], out_path: str, err_path: str) -> subprocess.CompletedProcess[str]:
        quoted = " ".join(shlex.quote(arg) for arg in args)
        command_line = (
            f"set -euo pipefail; mkdir -p {shlex.quote(cygwin_build)}; "
            f"cd {shlex.quote(cygwin_build)}; "
            f"{shlex.quote(cygwin_source + '/configure')} {quoted}"
        )
        result = subprocess.run(
            [resolved_bash, "-lc", command_line],
            cwd=source_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(result.stdout)
        with open(err_path, "w", encoding="utf-8") as handle:
            handle.write(result.stderr)
        return result

    result = run_once(configure_args, stdout_path, stderr_path)
    candidates = [
        os.path.join(build_dir, "config.h"),
        os.path.join(build_dir, "src", "config.h"),
        os.path.join(build_dir, "confdefs.h"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate, logs, notes

    if "--with-zlib" in configure_args and "zlib library missing" in (result.stdout + result.stderr):
        fallback_args = [arg for arg in configure_args if arg != "--with-zlib"]
        fallback_stdout = os.path.join(build_dir, "configure.fallback.stdout.txt")
        fallback_stderr = os.path.join(build_dir, "configure.fallback.stderr.txt")
        logs.extend([fallback_stdout, fallback_stderr])
        notes.append("Reference configure fell back to no-zlib mode.")
        run_once(fallback_args, fallback_stdout, fallback_stderr)
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate, logs, notes

    raise RuntimeError(f"autotools reference generation did not produce config.h. See logs: {', '.join(logs)}")


def prepare_reference_build_dir(
    reference_build_dir: str,
    *,
    clean: bool,
    rmtree=shutil.rmtree,
    unique_suffix: str | None = None,
) -> str:
    """Clean the reference dir, falling back to a fresh sibling on ACL failures."""
    if not clean or not os.path.isdir(reference_build_dir):
        return reference_build_dir

    try:
        rmtree(reference_build_dir)
        return reference_build_dir
    except PermissionError as exc:
        root = os.path.dirname(os.path.abspath(reference_build_dir))
        name = os.path.basename(os.path.abspath(reference_build_dir))
        suffix = unique_suffix or f"fresh_{os.getpid()}"
        candidate = os.path.join(root, f"{name}_{suffix}")
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(root, f"{name}_{suffix}_{counter}")
            counter += 1
        print(
            f"Warning: failed to clean {reference_build_dir}: {exc}. Using {candidate}.",
            file=sys.stderr,
        )
        return candidate


def compare_macros(
    reference: Dict[str, str],
    current: Dict[str, str],
    extra_exceptions: Dict[str, str] | None = None,
) -> Tuple[List[str], List[str], List[str]]:
    """Compare macro maps and return matches, accepted exceptions, and diffs."""
    matches: List[str] = []
    exceptions: List[str] = []
    diffs: List[str] = []
    reasons = dict(EXCEPTION_REASONS)
    if extra_exceptions:
        reasons.update(extra_exceptions)

    macro_names = sorted(name for name in set(reference) | set(current) if is_tracked_macro(name))
    for name in macro_names:
        reference_value = format_macro(reference, name)
        current_value = format_macro(current, name)
        if reference_value == current_value:
            matches.append(f"{name}={current_value}")
            continue
        message = f"{name}: reference={reference_value}, cmake={current_value}"
        if name in reasons:
            exceptions.append(f"{message} [{reasons[name]}]")
        else:
            diffs.append(message)
    return matches, exceptions, diffs


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    test_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    workspace_root = os.path.dirname(test_root)
    goaccess_root = os.path.join(workspace_root, "goaccess")
    parser = argparse.ArgumentParser(description="Compare GoAccess autotools/CMake config headers")
    parser.add_argument("--source-dir", default=goaccess_root)
    parser.add_argument("--cmake-config", default=os.path.join(goaccess_root, "build", "Debug", "config.h"))
    parser.add_argument("--cmake-cache")
    parser.add_argument("--reference-config")
    parser.add_argument("--generate-reference", action="store_true")
    parser.add_argument("--reference-build-dir", default=os.path.join(test_root, "build", "goaccess_autotools_ref"))
    parser.add_argument("--cygwin-bash", default="bash")
    parser.add_argument("--configure-arg", action="append", default=[])
    parser.add_argument("--report-file")
    parser.add_argument("--clean-reference-dir", action="store_true")
    return parser


def main() -> int:
    """CLI entry point."""
    parser = build_argument_parser()
    args = parser.parse_args()

    reference_logs: List[str] = []
    reference_notes: List[str] = []
    reference_source = args.reference_config
    configure_args = list(args.configure_arg)
    inferred_args: List[str] = []
    cmake_cache: Dict[str, str] = {}

    if not args.cmake_cache:
        candidate_cache = os.path.join(os.path.dirname(os.path.abspath(args.cmake_config)), "CMakeCache.txt")
        if os.path.isfile(candidate_cache):
            args.cmake_cache = candidate_cache

    if args.cmake_cache and os.path.isfile(args.cmake_cache):
        cmake_cache = parse_cmake_cache(args.cmake_cache)
        inferred_args = infer_configure_args(cmake_cache)
        if not configure_args:
            configure_args = inferred_args

    if args.generate_reference:
        args.reference_build_dir = prepare_reference_build_dir(
            args.reference_build_dir,
            clean=args.clean_reference_dir,
        )
        reference_source, reference_logs, reference_notes = run_reference_configure(
            bash_exe=args.cygwin_bash,
            source_dir=args.source_dir,
            build_dir=args.reference_build_dir,
            configure_args=configure_args,
        )

    if not reference_source:
        parser.error("Provide --reference-config or use --generate-reference.")
    if not os.path.isfile(reference_source):
        raise FileNotFoundError(f"Reference config not found: {reference_source}")
    if not os.path.isfile(args.cmake_config):
        raise FileNotFoundError(f"CMake config not found: {args.cmake_config}")

    extra_exceptions: Dict[str, str] = {}
    if any("no-zlib mode" in note for note in reference_notes):
        for macro in ("HAVE_LIBZ", "HAVE_ZLIB", "HAVE_ZLIB_H"):
            extra_exceptions[macro] = "Reference configure could not enable zlib."
    extra_exceptions.update(nls_disabled_exceptions(cmake_cache))

    matches, exceptions, diffs = compare_macros(
        parse_config_macros(reference_source),
        parse_config_macros(args.cmake_config),
        extra_exceptions=extra_exceptions,
    )

    lines = [
        "GoAccess parity report",
        f"Reference config: {reference_source}",
        f"CMake config: {args.cmake_config}",
        f"Matched macros: {len(matches)}",
        f"Allowed exceptions: {len(exceptions)}",
        f"Actionable differences: {len(diffs)}",
    ]
    if args.cmake_cache:
        lines.append(f"CMake cache: {args.cmake_cache}")
    if inferred_args:
        lines.append(f"Inferred configure args: {' '.join(inferred_args)}")
    if configure_args:
        lines.append(f"Used configure args: {' '.join(configure_args)}")
    if reference_logs:
        lines.append("Reference logs:")
        lines.extend(f"  {path}" for path in reference_logs)
    if reference_notes:
        lines.append("")
        lines.append("Reference notes:")
        lines.extend(f"  {note}" for note in reference_notes)
    if exceptions:
        lines.append("")
        lines.append("Allowed exceptions:")
        lines.extend(f"  {entry}" for entry in exceptions)
    if diffs:
        lines.append("")
        lines.append("Actionable differences:")
        lines.extend(f"  {entry}" for entry in diffs)

    report = "\n".join(lines)
    print(report)
    if args.report_file:
        with open(args.report_file, "w", encoding="utf-8") as handle:
            handle.write(report)
            handle.write("\n")
    return 0 if not diffs else 1


if __name__ == "__main__":
    sys.exit(main())
