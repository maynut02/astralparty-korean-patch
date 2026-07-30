from __future__ import annotations

from pathlib import Path

DEFAULT_ROUTE = "INT_STEAM"
DEFAULT_SNAPSHOT_FILE = "state/get_report.json"
LEGACY_SNAPSHOT_FILE = "state/assets_snapshot.json"

DEFAULT_GET_OUTPUT_DIR = "output_get"
DEFAULT_PATCH_OUTPUT_DIR = "output_patch"
DEFAULT_LANG_REPORT_FILE = "state/lang_report.json"
DEFAULT_STR_REPORT_FILE = "state/str_report.json"

# ROUTES_INT = ("INT_STEAM", "INT_ANDROID")
ROUTES_INT = ("INT_STEAM",)
ROUTES_CN = ("CN_BILIBILI", "CN_STEAM")
ROUTE_CHOICES = ROUTES_INT + ROUTES_CN
ROUTE_HOST_BY_PREFIX = {
    "INT_": "selist.feimogames.com",
    "CN_": "se-web-cn.feimogames.com",
}
HOTADDRESS_ROUTE_PARAM_BY_ROUTE = {
    "CN_BILIBILI": "CN_BILIBILI",
    "CN_STEAM": "CN_STEAM",
}

FILES_KO_DIR = Path("files_ko")
FILES_ORIGIN_DIR = Path("files_origin")

# INT_STEAM
# http://selist.feimogames.com:7878/api/hotaddressExtend/get?route=INT_STEAM&version=3.2.0

# INT_ANDROID
# http://selist.feimogames.com:7878/api/hotaddressExtend/get?route=INT_ANDROID&version=3.2.0

# CN_STEAM(110001933)
# http://se-web-cn.feimogames.com:7878/api/hotaddressExtend/get?route=CN_STEAM&version=3.2.0

# CN_BILIBILI(110001957)
# http://se-web-cn.feimogames.com:7878/api/hotaddressExtend/get?route=CN_BILIBILI&version=3.2.0
