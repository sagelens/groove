"""Runtime switches for the no-Rust Groove distribution."""

from __future__ import annotations

import os

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
PYTHON_ONLY_ENV = "HEADROOM_PYTHON_ONLY"


def is_python_only() -> bool:
    """Return whether native Rust components must be avoided."""
    return os.environ.get(PYTHON_ONLY_ENV, "").strip().lower() in _TRUE_VALUES


def apply_python_only_env() -> None:
    """Select Python/ONNX implementations before the proxy imports transforms."""
    if not is_python_only():
        return
    os.environ.setdefault("HEADROOM_REQUIRE_RUST_CORE", "false")
    os.environ.setdefault("HEADROOM_DETECT_BACKEND", "python")
    os.environ.setdefault("HEADROOM_KOMPRESS_BACKEND", "onnx_cpu")
    os.environ.setdefault(
        "HEADROOM_KOMPRESS_ONNX_FILENAME",
        "onnx/kompress-int8-wo.onnx",
    )
