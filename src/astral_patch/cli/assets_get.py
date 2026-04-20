from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx
import json
import os
import platform
from queue import Empty, Queue
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import (
    DEFAULT_GET_OUTPUT_DIR,
    DEFAULT_SNAPSHOT_FILE,
    HOTADDRESS_ROUTE_PARAM_BY_ROUTE,
    ROUTE_CHOICES,
    ROUTE_HOST_BY_PREFIX,
)
from ..paths import resolve_repo_path

HOTADDRESS_PATH_TEMPLATE = "http://{host}:7878/api/hotaddress/get?route={route}&version={version}"
APP_WEB_PREFIX = "{App.WebServerConfig.Path}/"
TARGET_TEXTASSET_NAMES = {
    "Simplified Chinese",
    "Traditional Chinese",
    "Japanese",
    "English",
    "STRCard",
}
TARGET_KEYWORDS = ("JingNanBoBoHei", "MochiyPopOne", "Afacad-Regular")
TARGET_KEYWORD_TYPES = {"font", "monobehaviour", "texture2d", "tex2d"}
TARGET_EXPORT_TYPES = "textAsset,font,monoBehaviour,tex2d"
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
DEFAULT_DOWNLOAD_WORKERS = 24
MAX_DOWNLOAD_WORKERS = 48
DEFAULT_MAX_BUNDLE_SIZE_MB = 20.0
ASSETSTUDIO_RELEASE_ZIP_BY_OS = {
    "windows": "https://github.com/aelurum/AssetStudio/releases/latest/download/AssetStudioModCLI_net9_win64.zip",
    "linux": "https://github.com/aelurum/AssetStudio/releases/latest/download/AssetStudioModCLI_net9_linux64.zip",
}
DEFAULT_ASSETSTUDIO_PATH_BY_OS = {
    "windows": Path("tools/AssetStudioModCLI/windows/AssetStudioModCLI.exe"),
    "linux": Path("tools/AssetStudioModCLI/linux/AssetStudioModCLI"),
}
LOG_LOCK = threading.Lock()
PROGRESS_LINE_ACTIVE = False


def detect_progress_enabled() -> bool:
    if os.getenv("ASTRAL_ASSETS_FORCE_PROGRESS", "").strip() == "1":
        return True
    if os.getenv("ASTRAL_ASSETS_NO_PROGRESS", "").strip() == "1":
        return False

    github_actions = os.getenv("GITHUB_ACTIONS", "").strip().lower()
    ci_flag = os.getenv("CI", "").strip().lower()
    if github_actions == "true":
        return False
    if ci_flag in {"1", "true", "yes"}:
        return False

    return sys.stdout.isatty()


PROGRESS_ENABLED = detect_progress_enabled()
USER_AGENT = "astral-assets-cli/0.1"
HTTP_CLIENT_LOCK = threading.Lock()
HTTP_CLIENT: httpx.Client | None = None
HTTP2_FALLBACK_WARNED = False


@dataclass
class PipelineResult:
    report: dict[str, Any]
    failure_count: int


class DownloadSkippedError(RuntimeError):
    pass


def create_http_client(max_connections: int = 64, max_keepalive_connections: int = 32) -> httpx.Client:
    global HTTP2_FALLBACK_WARNED

    limits = httpx.Limits(
        max_connections=max(1, int(max_connections)),
        max_keepalive_connections=max(1, int(max_keepalive_connections)),
    )
    try:
        return httpx.Client(
            follow_redirects=True,
            http2=True,
            headers={"User-Agent": USER_AGENT},
            limits=limits,
        )
    except ImportError:
        if not HTTP2_FALLBACK_WARNED:
            print(
                "[astral-assets] HTTP/2 unavailable (missing 'h2'); falling back to HTTP/1.1",
                file=sys.stderr,
                flush=True,
            )
            HTTP2_FALLBACK_WARNED = True
        return httpx.Client(
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            limits=limits,
        )


def get_http_client() -> httpx.Client:
    global HTTP_CLIENT
    if HTTP_CLIENT is None:
        with HTTP_CLIENT_LOCK:
            if HTTP_CLIENT is None:
                HTTP_CLIENT = create_http_client()
    return HTTP_CLIENT


def log(message: str) -> None:
    global PROGRESS_LINE_ACTIVE
    with LOG_LOCK:
        if PROGRESS_LINE_ACTIVE:
            print("")
            PROGRESS_LINE_ACTIVE = False
        print(message, flush=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_internal_id(value: str) -> str:
    return value.replace("\\", "/").strip()


def extract_bundle_names(catalog: dict[str, Any]) -> set[str]:
    bundles: set[str] = set()
    for raw in catalog.get("m_InternalIds", []):
        if not isinstance(raw, str):
            continue
        normalized = normalize_internal_id(raw)
        if not normalized.startswith(APP_WEB_PREFIX):
            continue
        suffix = normalized[len(APP_WEB_PREFIX):].strip("/")
        if not suffix:
            continue
        bundles.add(suffix)
    return bundles


def match_asset(asset_name: str, asset_type: str) -> bool:
    normalized_type = asset_type.lower().strip()
    if normalized_type == "textasset":
        return asset_name in TARGET_TEXTASSET_NAMES
    if normalized_type in TARGET_KEYWORD_TYPES:
        return any(keyword in asset_name for keyword in TARGET_KEYWORDS)
    return False


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return loaded


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    tmp_path = path.with_name(f"{path.stem}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def copy_reported_bundles(
    records: list[dict[str, str]],
    bundles_dir: Path,
    output_bundle_dir: Path,
) -> tuple[list[str], list[dict[str, str]]]:
    copied: list[str] = []
    copy_errors: list[dict[str, str]] = []
    target_bundle_names = sorted(
        {
            item.get("bundle_name", "")
            for item in records
            if isinstance(item, dict) and isinstance(item.get("bundle_name"), str) and item.get("bundle_name")
        }
    )
    if not target_bundle_names:
        return copied, copy_errors

    output_bundle_dir.mkdir(parents=True, exist_ok=True)
    for bundle_name in target_bundle_names:
        src = bundles_dir / bundle_name
        dst = output_bundle_dir / bundle_name
        try:
            if not src.exists():
                raise FileNotFoundError(f"Source bundle not found: {src}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(bundle_name)
        except Exception as exc:
            copy_errors.append({"bundle_name": bundle_name, "error": str(exc)})
    return copied, copy_errors


def render_progress_bar(current: int, total: int, width: int = 30) -> str:
    if total <= 0:
        percent = 0
    else:
        percent = int((current / total) * 100)
    percent = max(0, min(100, percent))
    filled = int((percent / 100) * width)
    full_block = "\u2588"
    light_block = "\u2592"
    return f"[{full_block * filled}{light_block * (width - filled)}] {percent:3d}%"


def update_progress_line(current: int, total: int, prefix: str = "Progress") -> None:
    global PROGRESS_LINE_ACTIVE
    if not PROGRESS_ENABLED:
        return

    progress_text = render_progress_bar(current=current, total=total)
    line = f"{prefix} {progress_text} ({current}/{total})"
    with LOG_LOCK:
        print(f"\r{line}", end="", flush=True)
        PROGRESS_LINE_ACTIVE = True


def update_pipeline_progress(
    download_done: int,
    download_total: int,
    asset_done: int,
    asset_total: int,
) -> None:
    global PROGRESS_LINE_ACTIVE
    if not PROGRESS_ENABLED:
        return

    dl_bar = render_progress_bar(download_done, download_total, width=20)
    as_bar = render_progress_bar(asset_done, asset_total, width=20)
    line = (
        f"DL {dl_bar} ({download_done}/{download_total}) | "
        f"AS {as_bar} ({asset_done}/{asset_total})"
    )
    with LOG_LOCK:
        print(f"\r{line}", end="", flush=True)
        PROGRESS_LINE_ACTIVE = True


def finish_progress_line() -> None:
    global PROGRESS_LINE_ACTIVE
    if not PROGRESS_ENABLED:
        return

    with LOG_LOCK:
        if PROGRESS_LINE_ACTIVE:
            print("")
            PROGRESS_LINE_ACTIVE = False


def sanitize_path_segment(value: str) -> str:
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", value).strip()
    return sanitized or "unknown"


def extract_source_revision(source_url: str) -> str:
    parsed = urllib.parse.urlparse(source_url)
    segments = [seg for seg in parsed.path.split("/") if seg]
    if not segments:
        return "unknown"
    return sanitize_path_segment(segments[-1])


def get_target_routes(route_arg: str) -> list[str]:
    route_value = (route_arg or "").strip()
    if not route_value:
        raise ValueError("--route cannot be empty")

    route_upper = route_value.upper()
    if route_upper == "ALL":
        return list(ROUTE_CHOICES)
    return [route_upper]


def resolve_hotaddress_route_param(route: str) -> str:
    return HOTADDRESS_ROUTE_PARAM_BY_ROUTE.get(route, route)


def build_hotaddress_get_url(route: str, version: str) -> str:
    host: str | None = None
    for prefix, mapped_host in ROUTE_HOST_BY_PREFIX.items():
        if route.startswith(prefix):
            host = mapped_host
            break

    if host is None:
        raise ValueError(f"Unsupported route prefix for hotaddress host mapping: {route}")

    route_param = urllib.parse.quote(resolve_hotaddress_route_param(route), safe="")
    version_param = urllib.parse.quote(version, safe="")
    return HOTADDRESS_PATH_TEMPLATE.format(host=host, route=route_param, version=version_param)


def cleanup_work_dir(work_dir: Path) -> bool:
    if not work_dir.exists():
        return False

    resolved = work_dir.resolve()
    cwd = Path.cwd().resolve()

    # Guard against deleting current workspace or a filesystem root.
    if resolved == cwd or resolved.parent == resolved:
        raise RuntimeError(f"Refusing to delete unsafe work directory: {resolved}")

    shutil.rmtree(resolved)
    return True


def fetch_json(url: str, timeout: int = 30, client: httpx.Client | None = None) -> dict[str, Any]:
    scoped_client = client or get_http_client()
    response = scoped_client.get(url, timeout=timeout)
    response.raise_for_status()
    loaded = response.json()
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected object JSON response from {url}")
    return loaded


def download_file(
    url: str,
    destination: Path,
    retries: int = 2,
    timeout: int = 120,
    max_bytes: int | None = None,
    client: httpx.Client | None = None,
) -> None:
    scoped_client = client or get_http_client()
    ensure_parent(destination)
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        temp_path = destination.with_suffix(destination.suffix + ".part")
        try:
            with scoped_client.stream("GET", url, timeout=timeout) as response:
                response.raise_for_status()
                expected_size_header = response.headers.get("Content-Length")
                if max_bytes is not None and expected_size_header:
                    try:
                        expected_size = int(expected_size_header)
                    except ValueError:
                        expected_size = -1
                    if expected_size > max_bytes:
                        raise DownloadSkippedError(
                            f"Skipped by size limit ({expected_size} bytes > {max_bytes} bytes)"
                        )

                written = 0
                with temp_path.open("wb") as out:
                    for chunk in response.iter_bytes(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        if not chunk:
                            continue
                        written += len(chunk)
                        if max_bytes is not None and written > max_bytes:
                            raise DownloadSkippedError(
                                f"Skipped by size limit while streaming ({written} bytes > {max_bytes} bytes)"
                            )
                        out.write(chunk)

            temp_path.replace(destination)
            return
        except DownloadSkippedError as exc:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise exc
        except (httpx.HTTPError, TimeoutError, OSError, KeyboardInterrupt) as exc:
            last_error = exc
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            if isinstance(exc, KeyboardInterrupt):
                raise
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"Failed to download {url}: {last_error}") from last_error


def detect_platform_key() -> str:
    system_name = platform.system().lower()
    if system_name.startswith("win"):
        return "windows"
    if system_name.startswith("linux"):
        return "linux"
    return ""


def default_assetstudio_path() -> Path:
    platform_key = detect_platform_key()
    if platform_key in DEFAULT_ASSETSTUDIO_PATH_BY_OS:
        return DEFAULT_ASSETSTUDIO_PATH_BY_OS[platform_key]
    return Path("AssetStudioModCLI_net9_win64/AssetStudioModCLI.exe")


def ensure_executable_permission(path: Path, platform_key: str) -> None:
    if platform_key == "windows":
        return
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def find_assetstudio_executable(search_root: Path, platform_key: str) -> Path | None:
    preferred_names = ["AssetStudioModCLI.exe"] if platform_key == "windows" else ["AssetStudioModCLI"]
    preferred_set = {name.lower() for name in preferred_names}

    preferred_matches: list[Path] = []
    fallback_matches: list[Path] = []

    for file_path in search_root.rglob("*"):
        if not file_path.is_file():
            continue
        name_lower = file_path.name.lower()
        if name_lower in preferred_set:
            preferred_matches.append(file_path)
            continue
        if name_lower.startswith("assetstudiomodcli"):
            fallback_matches.append(file_path)

    if preferred_matches:
        return sorted(preferred_matches, key=lambda item: (len(item.as_posix()), item.as_posix()))[0]
    if fallback_matches:
        return sorted(fallback_matches, key=lambda item: (len(item.as_posix()), item.as_posix()))[0]
    return None


def _has_assetstudio_runtime_files(path: Path, platform_key: str) -> bool:
    root = path.parent
    if platform_key == "windows":
        deps = root / f"{path.stem}.deps.json"
        runtime = root / f"{path.stem}.runtimeconfig.json"
        has_dll = any(root.glob("*.dll"))
        return deps.exists() and runtime.exists() and has_dll

    if platform_key == "linux":
        return any(root.glob("*.so"))

    return True


def ensure_assetstudio_executable(
    path: Path,
    auto_download: bool,
    retries: int,
    timeout: int,
) -> Path:
    platform_key = detect_platform_key()

    if path.exists():
        ensure_executable_permission(path, platform_key)
        if (not auto_download) or _has_assetstudio_runtime_files(path, platform_key):
            return path
        log(f"[astral-assets] AssetStudio runtime files missing near executable; reinstalling: {path.as_posix()}")
    elif not auto_download:
        raise FileNotFoundError(f"AssetStudio executable not found: {path}")

    release_zip_url = ASSETSTUDIO_RELEASE_ZIP_BY_OS.get(platform_key, "")
    if not release_zip_url:
        raise RuntimeError(
            f"Unsupported OS for auto-downloading AssetStudio CLI: {platform.system()} "
            f"(set --assetstudio-path manually)"
        )

    ensure_parent(path)
    log(f"[astral-assets] AssetStudio not found; downloading: {release_zip_url}")

    zip_path = path.parent / f"{path.stem}.download.zip"
    extract_dir_obj: tempfile.TemporaryDirectory[str] | None = None
    try:
        download_file(
            release_zip_url,
            zip_path,
            retries=max(0, retries),
            timeout=max(1, timeout),
        )
        extract_dir_obj = tempfile.TemporaryDirectory(prefix="assetstudio_extract_", dir=path.parent)
        extract_dir = Path(extract_dir_obj.name)

        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(extract_dir)

        discovered = find_assetstudio_executable(extract_dir, platform_key)
        if discovered is None:
            raise RuntimeError(f"AssetStudio executable not found in archive: {release_zip_url}")

        source_root = discovered.parent
        for child in source_root.iterdir():
            dst = path.parent / child.name
            if child.is_dir():
                shutil.copytree(child, dst, dirs_exist_ok=True)
            else:
                ensure_parent(dst)
                shutil.copy2(child, dst)

        final_executable = path if path.exists() else (path.parent / discovered.name)
        if not final_executable.exists():
            raise RuntimeError(f"Failed to place AssetStudio executable at expected path: {final_executable}")

        ensure_executable_permission(final_executable, platform_key)
        log(f"[astral-assets] AssetStudio prepared: {final_executable.as_posix()}")
        return final_executable
    finally:
        if extract_dir_obj is not None:
            extract_dir_obj.cleanup()
        if zip_path.exists():
            zip_path.unlink(missing_ok=True)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Astral asset incremental collection/analyzer CLI")
    parser.add_argument("--version", required=True, help="Game version, e.g. 3.0.1")
    parser.add_argument(
        "--route",
        default="ALL",
        help="Route for hotaddress API (e.g. INT_STEAM). Use ALL to process built-in default routes.",
    )
    parser.add_argument(
        "--work-dir",
        default="work",
        help="Workspace directory for downloaded catalogs/bundles/exports",
    )
    parser.add_argument(
        "--assetstudio-path",
        default=str(default_assetstudio_path()),
        help="Path to AssetStudioModCLI executable",
    )
    parser.add_argument(
        "--assetstudio-auto-download",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Auto-download AssetStudioModCLI when --assetstudio-path does not exist",
    )
    parser.add_argument("--output-dir", default=DEFAULT_GET_OUTPUT_DIR, help="Base output directory")
    parser.add_argument(
        "--report-file",
        default="",
        help="Optional single-route report path override (if set, report is written here)",
    )
    parser.add_argument(
        "--max-added-bundles",
        type=int,
        default=0,
        help="Process at most N bundles from catalog (0 means all)",
    )
    parser.add_argument(
        "--shard-count",
        type=int,
        default=1,
        help="Split target bundle list into N shards (default: 1)",
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        default=0,
        help="0-based shard index to process when --shard-count > 1",
    )
    parser.add_argument(
        "--download-retries",
        type=int,
        default=2,
        help="Retry count for bundle/catalog downloads",
    )
    parser.add_argument(
        "--download-timeout",
        type=int,
        default=120,
        help="Download timeout (seconds) per request",
    )
    parser.add_argument(
        "--max-bundle-size-mb",
        type=float,
        default=DEFAULT_MAX_BUNDLE_SIZE_MB,
        help="Skip bundle downloads larger than N MB (0 disables)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=6,
        help="Parallel workers for bundle processing",
    )
    parser.add_argument(
        "--save-reported-bundles",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Copy bundles referenced by report records into the route/version output folder",
    )
    parser.add_argument(
        "--cleanup-work",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Delete work directory after completion",
    )
    parser.add_argument(
        "--snapshot-file",
        default=DEFAULT_SNAPSHOT_FILE,
        help="Snapshot metadata path shared by other packages",
    )
    return parser


def get_type_from_path(export_path: Path, bundle_export_dir: Path) -> str:
    relative = export_path.relative_to(bundle_export_dir)
    if len(relative.parts) < 2:
        return ""
    return relative.parts[0]


def collect_matches_for_bundle(
    bundle_name: str,
    bundle_export_dir: Path,
) -> list[dict[str, str]]:
    if not bundle_export_dir.exists():
        return []

    records: list[dict[str, str]] = []
    for file_path in bundle_export_dir.rglob("*"):
        if not file_path.is_file():
            continue
        asset_type = get_type_from_path(file_path, bundle_export_dir)
        if not asset_type:
            continue
        asset_name = file_path.stem
        if not match_asset(asset_name=asset_name, asset_type=asset_type):
            continue
        records.append(
            {
                "asset_name": asset_name,
                "asset_type": asset_type,
                "bundle_name": bundle_name,
            }
        )
    return records


def run_assetstudio_export(assetstudio_path: Path, bundle_path: Path, bundle_export_dir: Path) -> None:
    bundle_export_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(assetstudio_path),
        str(bundle_path),
        "-m",
        "export",
        "-t",
        TARGET_EXPORT_TYPES,
        "-g",
        "type",
        "-f",
        "assetName",
        "-o",
        str(bundle_export_dir),
        "-r",
        "--log-level",
        "warning",
    ]
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"AssetStudio export failed for {bundle_path.name} "
            f"(exit={result.returncode}): {result.stdout[-2000:]}"
        )


def download_single_bundle(
    bundle_name: str,
    source_url: str,
    bundles_dir: Path,
    download_retries: int,
    download_timeout: int,
    max_bundle_bytes: int | None,
) -> dict[str, Any]:
    bundle_url = f"{source_url}/{bundle_name}"
    bundle_path = bundles_dir / bundle_name
    try:
        if not bundle_path.exists():
            download_file(
                bundle_url,
                bundle_path,
                retries=download_retries,
                timeout=download_timeout,
                max_bytes=max_bundle_bytes,
            )
        return {"bundle_name": bundle_name, "ok": True, "skipped": False, "error": ""}
    except DownloadSkippedError as exc:
        return {"bundle_name": bundle_name, "ok": False, "skipped": True, "error": str(exc)}
    except Exception as exc:
        return {"bundle_name": bundle_name, "ok": False, "skipped": False, "error": str(exc)}


def process_single_bundle(
    bundle_name: str,
    bundles_dir: Path,
    exports_dir: Path,
    assetstudio_path: Path,
) -> dict[str, Any]:
    bundle_path = bundles_dir / bundle_name
    try:
        if not bundle_path.exists():
            raise FileNotFoundError(f"Bundle not downloaded: {bundle_path}")

        bundle_export_dir = exports_dir / bundle_name
        run_assetstudio_export(
            assetstudio_path=assetstudio_path,
            bundle_path=bundle_path,
            bundle_export_dir=bundle_export_dir,
        )
        bundle_matches = collect_matches_for_bundle(
            bundle_name=bundle_name,
            bundle_export_dir=bundle_export_dir,
        )
        return {"bundle_name": bundle_name, "ok": True, "matches": bundle_matches, "error": ""}
    except Exception as exc:
        return {"bundle_name": bundle_name, "ok": False, "matches": [], "error": str(exc)}


def run_pipeline(args: argparse.Namespace, route_override: str | None = None) -> PipelineResult:
    run_at = utc_now_iso()
    version = args.version
    route = route_override or args.route
    work_dir = Path(args.work_dir)
    output_dir = Path(args.output_dir)
    assetstudio_path = Path(args.assetstudio_path)
    if not assetstudio_path.exists():
        raise FileNotFoundError(f"AssetStudio executable not found: {assetstudio_path}")

    catalog_dir = work_dir / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)

    failures: list[dict[str, str]] = []
    warnings: list[str] = []
    matched_records: list[dict[str, str]] = []

    get_url = build_hotaddress_get_url(route=route, version=version)
    log(f"[astral-assets] step 1/5 hotaddress lookup: route={route} version={version}")
    get_payload = fetch_json(get_url)
    source_url = get_payload.get("sourceUrl")
    if not isinstance(source_url, str) or not source_url:
        raise ValueError(f"Missing sourceUrl in get API response: {get_payload}")
    source_url = source_url.rstrip("/")
    source_revision = extract_source_revision(source_url)
    storage_scope = f"{route}/{version}/{source_revision}"
    log(f"[astral-assets] source_url={source_url}")
    log(f"[astral-assets] storage_scope={storage_scope}")

    report_override = str(getattr(args, "report_file", "") or "").strip()
    if report_override and route_override is None and route != "ALL":
        report_file = Path(report_override)
        output_bundle_dir = report_file.parent
    else:
        output_bundle_dir = output_dir / route / version / source_revision
        report_file = output_bundle_dir / "report.json"
    output_bundle_dir.mkdir(parents=True, exist_ok=True)

    bundles_dir = work_dir / "bundles" / route / version / source_revision
    exports_dir = work_dir / "exports" / route / version / source_revision / run_at.replace(":", "-")
    bundles_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    catalog_url = f"{source_url}/catalog_{version}.json"
    catalog_path = catalog_dir / f"catalog_{route}_{version}_{source_revision}.json"
    log("[astral-assets] step 2/5 catalog download")
    download_file(
        catalog_url,
        catalog_path,
        retries=max(0, int(args.download_retries)),
        timeout=max(1, int(args.download_timeout)),
    )
    catalog_payload = read_json_file(catalog_path)

    current_bundles = extract_bundle_names(catalog_payload)
    bundles_all = sorted(current_bundles)
    max_added = max(0, int(args.max_added_bundles))
    if max_added > 0:
        base_bundles = bundles_all[:max_added]
        if len(bundles_all) > len(base_bundles):
            warnings.append(
                "Processing limited by --max-added-bundles; remaining catalog bundles were skipped for this run."
            )
    else:
        base_bundles = bundles_all

    shard_count = max(1, int(getattr(args, "shard_count", 1)))
    shard_index = int(getattr(args, "shard_index", 0))
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError(f"Invalid shard selection: shard_index={shard_index}, shard_count={shard_count}")

    if shard_count > 1:
        bundles_to_process = [
            bundle_name
            for idx, bundle_name in enumerate(base_bundles)
            if (idx % shard_count) == shard_index
        ]
    else:
        bundles_to_process = base_bundles

    log(
        f"[astral-assets] step 3/5 target bundles: total={len(bundles_all)} "
        f"base={len(base_bundles)} to_process={len(bundles_to_process)} "
        f"shard={shard_index + 1}/{shard_count}",
    )

    downloaded_bundles: list[str] = []
    successful_bundles: list[str] = []
    interrupted = False
    max_workers = max(1, int(args.max_workers))
    download_retries = max(0, int(args.download_retries))
    download_timeout = max(1, int(args.download_timeout))
    max_bundle_size_mb = float(getattr(args, "max_bundle_size_mb", DEFAULT_MAX_BUNDLE_SIZE_MB))
    max_bundle_bytes = int(max_bundle_size_mb * 1024 * 1024) if max_bundle_size_mb > 0 else None
    skipped_bundle_count = 0

    if bundles_to_process:
        process_worker_count = min(max_workers, len(bundles_to_process))
        download_worker_count = min(
            max(DEFAULT_DOWNLOAD_WORKERS, max_workers * 4),
            MAX_DOWNLOAD_WORKERS,
            len(bundles_to_process),
        )
        process_backlog_limit = max(process_worker_count * 4, process_worker_count)
        log(
            f"[astral-assets] step 4/5 download+analyze pipeline start "
            f"(download_workers={download_worker_count}, process_workers={process_worker_count}, "
            f"retries={download_retries}, timeout={download_timeout}s, backlog={process_backlog_limit}, "
            f"max_bundle_size_mb={max_bundle_size_mb})"
        )
        download_done = 0
        asset_done = 0
        asset_total = len(bundles_to_process)
        process_submission_sem = threading.Semaphore(process_backlog_limit)
        process_completion_queue: Queue[Any] = Queue()
        process_futures: set[Any] = set()
        download_futures: dict[Any, str] = {}

        def on_process_done(future: Any) -> None:
            process_completion_queue.put(future)
            process_submission_sem.release()

        def drain_process_results(block: bool) -> None:
            nonlocal asset_done
            while True:
                try:
                    future = process_completion_queue.get(timeout=0.1 if block else 0)
                except Empty:
                    break

                bundle_name = str(getattr(future, "_bundle_name", ""))
                process_futures.discard(future)
                try:
                    result = future.result()
                    bundle_name = str(result.get("bundle_name", bundle_name))
                    if result.get("ok"):
                        successful_bundles.append(bundle_name)
                        matches = result.get("matches", [])
                        if isinstance(matches, list):
                            matched_records.extend(matches)
                    else:
                        failures.append(
                            {
                                "bundle_name": bundle_name,
                                "error": str(result.get("error", "Unknown error")),
                                "stage": "export",
                            }
                        )
                except Exception as exc:
                    failures.append(
                        {
                            "bundle_name": bundle_name or "(unknown)",
                            "error": str(exc),
                            "stage": "export",
                        }
                    )
                asset_done += 1

        try:
            update_pipeline_progress(
                download_done=0,
                download_total=len(bundles_to_process),
                asset_done=0,
                asset_total=asset_total,
            )
            with (
                ThreadPoolExecutor(max_workers=download_worker_count) as download_executor,
                ThreadPoolExecutor(max_workers=process_worker_count) as process_executor,
            ):
                for bundle_name in bundles_to_process:
                    future = download_executor.submit(
                        download_single_bundle,
                        bundle_name=bundle_name,
                        source_url=source_url,
                        bundles_dir=bundles_dir,
                        download_retries=download_retries,
                        download_timeout=download_timeout,
                        max_bundle_bytes=max_bundle_bytes,
                    )
                    download_futures[future] = bundle_name

                for future in as_completed(download_futures):
                    result = future.result()
                    bundle_name = str(result.get("bundle_name", download_futures[future]))
                    download_done += 1
                    if result.get("ok"):
                        downloaded_bundles.append(bundle_name)
                        process_submission_sem.acquire()
                        process_future = process_executor.submit(
                            process_single_bundle,
                            bundle_name=bundle_name,
                            bundles_dir=bundles_dir,
                            exports_dir=exports_dir,
                            assetstudio_path=assetstudio_path,
                        )
                        setattr(process_future, "_bundle_name", bundle_name)
                        process_futures.add(process_future)
                        process_future.add_done_callback(on_process_done)
                    else:
                        if bool(result.get("skipped")):
                            skipped_bundle_count += 1
                        else:
                            failures.append(
                                {
                                    "bundle_name": bundle_name,
                                    "error": str(result.get("error", "Unknown error")),
                                    "stage": "download",
                                }
                            )
                        asset_done += 1
                    drain_process_results(block=False)
                    update_pipeline_progress(
                        download_done=download_done,
                        download_total=len(bundles_to_process),
                        asset_done=asset_done,
                        asset_total=asset_total,
                    )

                while process_futures:
                    drain_process_results(block=True)
                    update_pipeline_progress(
                        download_done=download_done,
                        download_total=len(bundles_to_process),
                        asset_done=asset_done,
                        asset_total=asset_total,
                    )
            finish_progress_line()
            log("[astral-assets] step 5/5 pipeline finished")
        except KeyboardInterrupt:
            finish_progress_line()
            interrupted = True
            warnings.append("Interrupted by user; pipeline stopped before completion.")
            failures.append({"bundle_name": "(batch)", "error": "Interrupted by user"})
        except Exception:
            finish_progress_line()
            raise

    if bundles_to_process and not downloaded_bundles and not interrupted:
        warnings.append("All target bundle downloads failed; export was skipped.")

    if skipped_bundle_count > 0:
        warnings.append(f"Bundles skipped by size limit: {skipped_bundle_count}")

    if not bundles_all:
        warnings.append("No target bundle detected in catalog. Download/export skipped.")

    copied_bundle_names: list[str] = []
    bundle_copy_errors: list[dict[str, str]] = []
    if getattr(args, "save_reported_bundles", True):
        copied_bundle_names, bundle_copy_errors = copy_reported_bundles(
            records=matched_records,
            bundles_dir=bundles_dir,
            output_bundle_dir=output_bundle_dir,
        )
        if copied_bundle_names:
            log(
                f"[astral-assets] copied reported bundles: "
                f"{len(copied_bundle_names)} -> {output_bundle_dir.as_posix()}"
            )
        if bundle_copy_errors:
            warnings.append(
                f"Some reported bundles failed to copy to output: {len(bundle_copy_errors)}"
            )

    report_payload: dict[str, Any] = {
        "summary": {
            "route": route,
            "version": version,
            "source_revision": source_revision,
            "run_at": run_at,
            "source_url": source_url,
            "current_bundle_count": len(current_bundles),
            "added_bundle_count": len(bundles_all),
            "processed_bundle_count": len(bundles_to_process),
            "downloaded_bundle_count": len(downloaded_bundles),
            "exported_bundle_count": len(successful_bundles),
            "matched_asset_count": len(matched_records),
            "shard_index": shard_index,
            "shard_count": shard_count,
            "failed_bundles": failures,
            "skipped_bundle_count": skipped_bundle_count,
            "warnings": warnings,
            "interrupted": interrupted,
            "catalog_diff_enabled": False,
            "copied_reported_bundle_count": len(copied_bundle_names),
            "copied_reported_bundles_path": output_bundle_dir.as_posix() if copied_bundle_names else "",
            "bundle_copy_errors": bundle_copy_errors,
            "report_path": report_file.as_posix(),
        },
        "records": matched_records,
    }
    write_json_file(report_file, report_payload)
    return PipelineResult(report=report_payload, failure_count=len(failures))


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    args.work_dir = resolve_repo_path(args.work_dir).as_posix()
    args.output_dir = resolve_repo_path(args.output_dir).as_posix()
    args.snapshot_file = resolve_repo_path(args.snapshot_file).as_posix()
    args.assetstudio_path = resolve_repo_path(args.assetstudio_path).as_posix()
    if str(args.report_file or "").strip():
        args.report_file = resolve_repo_path(args.report_file).as_posix()

    assetstudio_path = ensure_assetstudio_executable(
        path=Path(args.assetstudio_path),
        auto_download=bool(getattr(args, "assetstudio_auto_download", True)),
        retries=max(0, int(args.download_retries)),
        timeout=max(1, int(args.download_timeout)),
    )
    args.assetstudio_path = assetstudio_path.as_posix()

    target_routes = get_target_routes(args.route)
    results: list[PipelineResult] = []
    hard_failures = 0
    route_snapshots: dict[str, dict[str, Any]] = {}

    try:
        for route in target_routes:
            log(f"[astral-assets] ===== route: {route} =====")
            try:
                result = run_pipeline(args, route_override=route)
                results.append(result)
                summary = result.report.get("summary", {})
                route_snapshots[route] = {
                    "revision": str(summary.get("source_revision", "")),
                    "report_path": str(summary.get("report_path", "")),
                    "failed_count": len(summary.get("failed_bundles", [])) if isinstance(summary.get("failed_bundles", []), list) else 0,
                }
            except Exception as exc:
                hard_failures += 1
                route_snapshots[route] = {
                    "revision": "",
                    "report_path": "",
                    "failed_count": 0,
                    "error": str(exc),
                }
                print(f"[astral-assets] route {route} fatal error: {exc}", file=sys.stderr)
    except KeyboardInterrupt:
        print("[astral-assets] interrupted by user", file=sys.stderr)
        return 130

    if getattr(args, "cleanup_work", True):
        try:
            if cleanup_work_dir(Path(args.work_dir)):
                log(f"[astral-assets] cleaned work dir: {Path(args.work_dir).as_posix()}")
        except Exception as exc:
            print(f"[astral-assets] failed to cleanup work dir: {exc}", file=sys.stderr)

    total_added = sum(item.report["summary"]["added_bundle_count"] for item in results)
    total_downloaded = sum(item.report["summary"]["downloaded_bundle_count"] for item in results)
    total_matched = sum(item.report["summary"]["matched_asset_count"] for item in results)
    total_failed = sum(len(item.report["summary"]["failed_bundles"]) for item in results) + hard_failures
    total_routes = len(target_routes)
    print(
        "[astral-assets] "
        f"routes={total_routes} "
        f"added={total_added} "
        f"downloaded={total_downloaded} "
        f"matched={total_matched} "
        f"failed={total_failed}"
    )

    snapshot_path = Path(str(getattr(args, "snapshot_file", DEFAULT_SNAPSHOT_FILE) or DEFAULT_SNAPSHOT_FILE))
    snapshot_payload: dict[str, Any] = {
        "generated_at": utc_now_iso(),
        "version": args.version,
        "routes": route_snapshots,
    }
    try:
        write_json_atomic(snapshot_path, snapshot_payload)
        log(f"[astral-assets] snapshot updated: {snapshot_path.as_posix()}")
    except Exception as exc:
        print(f"[astral-assets] failed to update snapshot: {exc}", file=sys.stderr)

    if hard_failures > 0:
        return 2
    return 1 if total_failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
