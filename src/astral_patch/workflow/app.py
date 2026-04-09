from __future__ import annotations

import argparse
from typing import Callable

from . import (
    build_patch_zips,
    build_release_meta,
    build_sync_commit_message,
    delete_run_artifacts,
    extract_shard_report,
    merge_get_reports,
    merge_get_snapshots,
    plan_get_shards,
    prune_output_get,
    update_workflow_readme,
    validate_workflow_layout,
)


CommandMain = Callable[[list[str] | None], int]


COMMANDS: dict[str, tuple[str, CommandMain]] = {
    "build-patch-zips": ("Build release zip files from output_patch.", build_patch_zips.main),
    "build-release-meta": ("Write release metadata to GITHUB_OUTPUT.", build_release_meta.main),
    "build-sync-commit-message": ("Build workflow branch commit message.", build_sync_commit_message.main),
    "delete-run-artifacts": ("Delete the current GitHub Actions run artifacts.", delete_run_artifacts.main),
    "extract-shard-report": ("Extract one route report from a shard snapshot.", extract_shard_report.main),
    "merge-get-reports": ("Merge shard report files into route reports.", merge_get_reports.main),
    "merge-get-snapshots": ("Merge shard snapshots into state/get_report.json.", merge_get_snapshots.main),
    "plan-get-shards": ("Plan shard matrix for assets-get workflow jobs.", plan_get_shards.main),
    "prune-output-get": ("Prune output_get history per route.", prune_output_get.main),
    "update-workflow-readme": ("Rewrite workflow branch README summary.", update_workflow_readme.main),
    "validate-workflow-layout": ("Validate workflow branch layout.", validate_workflow_layout.main),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="astral-workflow",
        description="Unified workflow helper CLI for GitHub Actions jobs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, (help_text, _) in COMMANDS.items():
        subparsers.add_parser(name, help=help_text)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, remaining = parser.parse_known_args(argv)
    _, command_main = COMMANDS[args.command]
    return command_main(remaining)


if __name__ == "__main__":
    raise SystemExit(main())
