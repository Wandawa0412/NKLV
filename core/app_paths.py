"""Centralized runtime paths for bundled resources and writable app data."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from core.app_metadata import APP_DATA_DIRNAME


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _get_app_root() -> str:
    """Return the directory that contains the running executable or project."""
    if _is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_resource_root() -> str:
    """Return the location of bundled read-only resources."""
    if _is_frozen():
        return getattr(sys, "_MEIPASS", _get_app_root())
    return _get_app_root()


def _get_user_data_root() -> str:
    """Return the writable runtime data directory."""
    if _is_frozen():
        return os.path.join(_get_app_root(), ".temp")

    override = os.environ.get("NKLV_ECOS_DATA_DIR")
    if override:
        return os.path.abspath(override)

    return os.path.join(_get_app_root(), ".temp")


def _resolve_template_path(resource_root: str) -> str:
    """Resolve the bundled Excel template without hardcoding a locale-sensitive filename."""
    template_dir = Path(resource_root) / "Template excel"
    preferred_ascii_name = "1.Nhat ky lam viec 2026.xlsx"
    preferred_ascii_path = template_dir / preferred_ascii_name
    if preferred_ascii_path.exists():
        return str(preferred_ascii_path)

    candidates = sorted(template_dir.glob("*.xlsx"))
    if candidates:
        return str(candidates[0])

    return str(preferred_ascii_path)


def _copy_tree_contents(source_root: str, target_root: str) -> None:
    os.makedirs(target_root, exist_ok=True)
    for entry in os.listdir(source_root):
        source = os.path.join(source_root, entry)
        target = os.path.join(target_root, entry)
        if os.path.isdir(source):
            shutil.copytree(source, target, dirs_exist_ok=True)
        elif not os.path.exists(target):
            shutil.copy2(source, target)


def _legacy_user_data_candidates(app_root: str) -> list[str]:
    candidates: list[str] = []

    side_by_side = os.path.join(app_root, ".temp")
    candidates.append(side_by_side)

    for env_name in ("LOCALAPPDATA", "APPDATA"):
        base_dir = os.environ.get(env_name)
        if not base_dir:
            continue
        candidates.append(os.path.join(base_dir, APP_DATA_DIRNAME))

    ordered: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = os.path.abspath(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _migrate_legacy_user_data(app_root: str, user_data_root: str):
    """Migrate older runtime data roots into the current side-by-side `.temp` folder."""
    if not _is_frozen():
        return
    if os.path.exists(os.path.join(user_data_root, "worklog.db")):
        return

    target_root = os.path.abspath(user_data_root)
    for candidate in _legacy_user_data_candidates(app_root):
        if candidate == target_root or not os.path.isdir(candidate):
            continue
        if not os.path.exists(os.path.join(candidate, "worklog.db")):
            continue
        _copy_tree_contents(candidate, target_root)
        return


APP_ROOT = _get_app_root()
RESOURCE_ROOT = _get_resource_root()
USER_DATA_ROOT = _get_user_data_root()
_migrate_legacy_user_data(APP_ROOT, USER_DATA_ROOT)

# Backward-compatible aliases used throughout the current codebase.
TEMP_DIR = USER_DATA_ROOT
DB_PATH = os.path.join(USER_DATA_ROOT, "worklog.db")
OUTPUT_DIR = os.path.join(USER_DATA_ROOT, "output")
TEMPLATE_PATH = _resolve_template_path(RESOURCE_ROOT)

os.makedirs(USER_DATA_ROOT, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
