#!/usr/bin/env python3
"""Prepare, verify, and run Groove without Rust or automatic model downloads."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RESOURCES = ROOT / "resources"
MANIFEST_PATH = RESOURCES / "assets-manifest.json"
MODEL_CONFIG = RESOURCES / "config" / "models.json"
MODEL_CONFIG_EXAMPLE = RESOURCES / "config" / "models.example.json"


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _assets(packs: list[str]) -> list[dict[str, Any]]:
    manifest = _manifest()
    available = manifest["packs"]
    unknown = sorted(set(packs) - set(available))
    if unknown:
        raise SystemExit(f"Unknown asset pack(s): {', '.join(unknown)}")
    return [asset for pack in packs for asset in available[pack]]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare(packs: list[str], model: str | None, context_window: int, force: bool) -> int:
    assets = _assets(packs)
    for asset in assets:
        (RESOURCES / asset["destination"]).parent.mkdir(parents=True, exist_ok=True)

    MODEL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    if model:
        config = {
            "openai": {
                "context_limits": {model: context_window},
                "pricing": {model: [0, 0]},
                "encodings": {model: "o200k_base"},
            }
        }
        if force or not MODEL_CONFIG.exists():
            MODEL_CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    elif not MODEL_CONFIG.exists():
        shutil.copyfile(MODEL_CONFIG_EXAMPLE, MODEL_CONFIG)

    print("Directories prepared. Download each file manually:")
    for asset in assets:
        print(
            f"\n{asset['name']}\n  from: {asset['url']}\n  to:   {RESOURCES / asset['destination']}"
        )
    print(f"\nModel limits: {MODEL_CONFIG}")
    return 0


def verify(packs: list[str]) -> int:
    failed = False
    for asset in _assets(packs):
        path = RESOURCES / asset["destination"]
        if not path.is_file():
            print(f"MISSING  {path}")
            failed = True
            continue
        size = path.stat().st_size
        if size != asset["size"]:
            print(f"BAD SIZE {path} ({size}, expected {asset['size']})")
            failed = True
            continue
        actual = _sha256(path)
        if actual != asset["sha256"]:
            print(f"BAD HASH {path}")
            failed = True
            continue
        print(f"OK       {asset['name']}")
    return 1 if failed else 0


def _validate_model_config() -> None:
    if not MODEL_CONFIG.is_file():
        raise SystemExit(f"Missing {MODEL_CONFIG}; run `python groove.py prepare --model NAME`.")
    text = MODEL_CONFIG.read_text(encoding="utf-8")
    if "replace-with-your-local-model-name" in text:
        raise SystemExit(
            f"Edit {MODEL_CONFIG} with the exact model name returned by your local /v1/models."
        )


def _check_upstream(upstream: str) -> None:
    url = upstream.rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]
    request = urllib.request.Request(
        f"{url}/v1/models",
        headers={"Authorization": "Bearer local"},
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            if response.status >= 400:
                raise SystemExit(f"Local LLM endpoint returned HTTP {response.status}.")
    except (OSError, urllib.error.URLError) as exc:
        raise SystemExit(f"Cannot reach local LLM endpoint at {url}: {exc}") from exc


def run(upstream: str, host: str, port: int, skip_asset_check: bool) -> int:
    if not skip_asset_check and verify(["core"]):
        raise SystemExit("Core assets are incomplete. See `python groove.py prepare --help`.")
    _validate_model_config()
    _check_upstream(upstream)

    env = os.environ
    env["HEADROOM_PYTHON_ONLY"] = "1"
    env["HEADROOM_OFFLINE"] = "1"
    env["HEADROOM_BINARIES_OFFLINE"] = "1"
    env["HEADROOM_REQUIRE_RUST_CORE"] = "false"
    env["HEADROOM_DETECT_BACKEND"] = "python"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["HF_HOME"] = str(RESOURCES / "hf")
    env["HF_HUB_CACHE"] = str(RESOURCES / "hf" / "hub")
    env["FASTEMBED_CACHE_PATH"] = str(RESOURCES / "hf" / "hub")
    env["TIKTOKEN_CACHE_DIR"] = str(RESOURCES / "tiktoken")
    env["HEADROOM_MODEL_LIMITS"] = str(MODEL_CONFIG)
    env["HEADROOM_KOMPRESS_BACKEND"] = "onnx_cpu"
    env["HEADROOM_KOMPRESS_ONNX_FILENAME"] = "onnx/kompress-int8-wo.onnx"
    env["OPENAI_TARGET_API_URL"] = upstream.rstrip("/")
    env.setdefault("OPENAI_API_KEY", "local")
    no_proxy = env.get("NO_PROXY", env.get("no_proxy", ""))
    entries = [entry for entry in no_proxy.split(",") if entry]
    for loopback in ("127.0.0.1", "localhost"):
        if loopback not in entries:
            entries.append(loopback)
    env["NO_PROXY"] = ",".join(entries)
    env["no_proxy"] = env["NO_PROXY"]

    argv = [
        sys.executable,
        "-m",
        "headroom.cli",
        "proxy",
        "--host",
        host,
        "--port",
        str(port),
        "--no-http2",
        "--request-timeout-seconds",
        "600",
    ]
    os.execve(sys.executable, argv, env)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="Create directories and print URLs")
    prepare_parser.add_argument(
        "--pack",
        action="append",
        choices=["core", "memory", "image", "relevance"],
        dest="packs",
        help="Asset pack to prepare; repeat for multiple packs (default: core)",
    )
    prepare_parser.add_argument("--model", help="Exact local model ID from /v1/models")
    prepare_parser.add_argument("--context-window", type=int, default=32768)
    prepare_parser.add_argument("--force", action="store_true", help="Replace models.json")

    verify_parser = subparsers.add_parser("verify", help="Check manually downloaded assets")
    verify_parser.add_argument(
        "--pack",
        action="append",
        choices=["core", "memory", "image", "relevance"],
        dest="packs",
        help="Asset pack to verify; repeat for multiple packs (default: core)",
    )

    run_parser = subparsers.add_parser("run", help="Start the local Python-only proxy")
    run_parser.add_argument("--upstream", default="http://127.0.0.1:4142")
    run_parser.add_argument("--host", default="127.0.0.1")
    run_parser.add_argument("--port", type=int, default=8787)
    run_parser.add_argument("--skip-asset-check", action="store_true")

    args = parser.parse_args()
    if args.command == "prepare":
        return prepare(args.packs or ["core"], args.model, args.context_window, args.force)
    if args.command == "verify":
        return verify(args.packs or ["core"])
    return run(args.upstream, args.host, args.port, args.skip_asset_check)


if __name__ == "__main__":
    raise SystemExit(main())
