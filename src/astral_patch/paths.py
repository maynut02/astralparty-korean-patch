from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_MARKERS = ("pyproject.toml", ".git")


def _has_repo_markers(path: Path) -> bool:
    return any((path / marker).exists() for marker in REPO_MARKERS)


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if _has_repo_markers(candidate):
            return candidate

    raise FileNotFoundError(
        f"Unable to find repository root from: {current.as_posix()}"
    )


def resolve_repo_path(value: str | Path, *, repo_root: Path | None = None) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return find_repo_root(repo_root) / path


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    src: Path
    state: Path
    output_get: Path
    output_patch: Path
    files_ko: Path
    files_origin: Path
    tools: Path

    def resolve(self, value: str | Path) -> Path:
        return resolve_repo_path(value, repo_root=self.root)


def project_paths(start: Path | None = None) -> ProjectPaths:
    root = find_repo_root(start)
    return ProjectPaths(
        root=root,
        src=root / "src",
        state=root / "state",
        output_get=root / "output_get",
        output_patch=root / "output_patch",
        files_ko=root / "files_ko",
        files_origin=root / "files_origin",
        tools=root / "tools",
    )


def resolve_many(values: Iterable[str | Path], *, repo_root: Path | None = None) -> list[Path]:
    return [resolve_repo_path(value, repo_root=repo_root) for value in values]
