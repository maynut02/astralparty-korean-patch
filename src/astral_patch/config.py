from __future__ import annotations

from pathlib import Path

DEFAULT_ROUTE = "INT_STEAM"
DEFAULT_SNAPSHOT_FILE = "state/get_report.json"
LEGACY_SNAPSHOT_FILE = "state/assets_snapshot.json"

DEFAULT_GET_OUTPUT_DIR = "output_get"
DEFAULT_PATCH_OUTPUT_DIR = "output_patch"
DEFAULT_LANG_REPORT_FILE = "state/lang_report.json"
DEFAULT_STR_REPORT_FILE = "state/str_report.json"

ROUTES_INT = ("INT_STEAM", "INT_ANDROID")
ROUTES_CN = ("CN_BILIBILI",)
ROUTE_CHOICES = ROUTES_INT + ROUTES_CN
ROUTE_HOST_BY_PREFIX = {
    "INT_": "selist.feimogames.com",
    "CN_": "se-web-cn.feimogames.com",
}
HOTADDRESS_ROUTE_PARAM_BY_ROUTE = {
    "CN_BILIBILI": "110001957",
}

FILES_KO_DIR = Path("files_ko")
FILES_ORIGIN_DIR = Path("files_origin")
