"""Importação segura de uma instalação anterior do Bot de Ofertas."""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import yaml

from .runtime_paths import PATHS, RuntimePaths


@dataclass(frozen=True)
class MigrationReport:
    source: str
    offers: int
    has_ml_profile: bool
    browser_reinstall_required: bool
    copied: tuple[str, ...]
    warnings: tuple[str, ...]


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _validate_source(source: Path) -> MigrationReport:
    source = source.resolve()
    if not source.is_dir():
        raise ValueError("A pasta selecionada não existe.")
    for relative in (".env", "config.yaml", "data/nichos.json"):
        path = source / relative
        if path.exists():
            path.read_text(encoding="utf-8")
    config_path = source / "config.yaml"
    if config_path.exists() and not isinstance(yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}, dict):
        raise ValueError("O config.yaml da instalação anterior é inválido.")
    niches_path = source / "data" / "nichos.json"
    if niches_path.exists() and not isinstance(json.loads(niches_path.read_text(encoding="utf-8")), list):
        raise ValueError("O nichos.json da instalação anterior é inválido.")

    offers = 0
    database = source / "data" / "ofertas.db"
    if database.exists():
        with closing(sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("O banco de ofertas da instalação anterior está corrompido.")
            row = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='postadas'"
            ).fetchone()
            if row[0]:
                offers = connection.execute("SELECT COUNT(*) FROM postadas").fetchone()[0]

    profile = source / "data" / "ml_profile"
    has_profile = profile.is_dir() and any(profile.iterdir())
    browser = source / "data" / "pw-browsers"
    warnings = ("O Chromium será reinstalado para garantir compatibilidade.",) if browser.exists() else ()
    return MigrationReport(str(source), offers, has_profile, browser.exists(), (), warnings)


def inspect_legacy(source: str | Path) -> MigrationReport:
    return _validate_source(Path(source))


def _copy_checked(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise ValueError(f"Links simbólicos não são aceitos na importação: {source.name}")
    if source.is_dir():
        for item in source.rglob("*"):
            if item.is_symlink() or not _inside(item, source):
                raise ValueError(f"Caminho inseguro na importação: {item.name}")
        shutil.copytree(source, destination)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def import_legacy(source: str | Path, destination: RuntimePaths = PATHS) -> MigrationReport:
    source_path = Path(source).resolve()
    report = _validate_source(source_path)
    if source_path == destination.user_root.resolve() or _inside(destination.user_root, source_path):
        raise ValueError("Escolha uma instalação diferente da pasta de destino do aplicativo.")

    destination.user_root.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=".bot-ofertas-import-", dir=destination.user_root.parent))
    staged_config = staging_root / "config"
    staged_data = staging_root / "data"
    staged_config.mkdir()
    staged_data.mkdir()
    copied: list[str] = []
    mapping = (
        (source_path / ".env", staged_config / ".env", ".env"),
        (source_path / "config.yaml", staged_config / "config.yaml", "config.yaml"),
        (source_path / "data" / "nichos.json", staged_data / "nichos.json", "data/nichos.json"),
        (source_path / "data" / "ofertas.db", staged_data / "ofertas.db", "data/ofertas.db"),
        (source_path / "data" / "ml_profile", staged_data / "ml_profile", "data/ml_profile"),
    )
    backups: list[tuple[Path, Path]] = []
    activated: list[Path] = []
    try:
        for origin, target, label in mapping:
            if origin.exists():
                _copy_checked(origin, target)
                copied.append(label)
        staged_report = _validate_source(staging_root)
        if staged_report.offers != report.offers:
            raise ValueError("A quantidade de ofertas mudou durante a cópia.")

        for staged, target in ((staged_config, destination.config_dir), (staged_data, destination.data_dir)):
            backup = target.with_name(target.name + ".before-import")
            if backup.exists():
                shutil.rmtree(backup) if backup.is_dir() else backup.unlink()
            if target.exists():
                target.replace(backup)
                backups.append((target, backup))
            staged.replace(target)
            activated.append(target)
        for _, backup in backups:
            shutil.rmtree(backup) if backup.is_dir() else backup.unlink(missing_ok=True)
    except Exception:
        for target in reversed(activated):
            if target.exists():
                shutil.rmtree(target) if target.is_dir() else target.unlink()
        for target, backup in reversed(backups):
            if backup.exists():
                backup.replace(target)
        raise
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)

    return MigrationReport(
        report.source,
        report.offers,
        report.has_ml_profile,
        report.browser_reinstall_required,
        tuple(copied),
        report.warnings,
    )
