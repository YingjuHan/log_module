#!/usr/bin/env python3
"""Shared CMake CLI helpers for CAE tooling."""

from __future__ import annotations

import argparse


def parse_cmake_option(value: str) -> tuple[str, str]:
    """Parse a repeated KEY=VALUE CMake option."""
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"Invalid --cmake-option '{value}'; expected KEY=VALUE")

    key, raw_value = value.split("=", 1)
    key = key.strip()
    if not key:
        raise argparse.ArgumentTypeError(f"Invalid --cmake-option '{value}'; key must not be empty")
    return key, raw_value


def should_pass_config(generator: str | None, config: str | None) -> bool:
    """Return whether build/install commands should include --config."""
    if not config or generator is None:
        return False
    return generator not in {"Ninja", "Unix Makefiles", "MinGW Makefiles", "NMake Makefiles"}
