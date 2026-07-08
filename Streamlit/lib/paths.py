"""Repository-relative paths for Streamlit dashboard assets."""

from __future__ import annotations

from pathlib import Path


def streamlit_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    return streamlit_dir().parent


def wikieval_json_path() -> Path:
    """Lokal export WikiEval (Bahasa Inggris), 50 item — lihat notebooks/01_analisis_dataset_wikieval.ipynb."""
    return repo_root() / "dataset" / "wikiEval_all.json"


def images_faithfulness_dir() -> Path:
    root = repo_root()
    direct = root / "Eval_Data" / "Images_Faithfulness_10"
    if direct.is_dir():
        return direct
    return root / "Images_Faithfulness_10"


def lightrag_backups_root() -> Path:
    return repo_root() / "LightRAG" / "backups"


def lightrag_live_rag_storage(locale: str) -> Path:
    """locale: 'en' | 'id'"""
    loc = locale.lower()
    if loc not in ("en", "id"):
        raise ValueError("locale must be 'en' or 'id'")
    return repo_root() / "LightRAG" / f"LightRAG-{loc}" / "data" / "rag_storage"


def list_pre_backup_bundles() -> list[str]:
    """Directory names under LightRAG/backups matching lightrag_pre_100pertanyaan_*."""
    root = lightrag_backups_root()
    if not root.is_dir():
        return []
    names = sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir() and p.name.startswith("lightrag_pre_100pertanyaan_")
    )
    return names


def list_all_backup_bundles() -> list[str]:
    root = lightrag_backups_root()
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))


def bundle_rag_storage(bundle_name: str, locale: str) -> Path:
    """Path to rag_storage inside a backup bundle: .../lightrag-{en|id}/rag_storage."""
    loc = locale.lower()
    if loc not in ("en", "id"):
        raise ValueError("locale must be 'en' or 'id'")
    return lightrag_backups_root() / bundle_name / f"lightrag-{loc}" / "rag_storage"


def default_pre_backup_bundle() -> str | None:
    bundles = list_pre_backup_bundles()
    return bundles[-1] if bundles else None


def data_backups_root() -> Path:
    return repo_root() / "data" / "backups"


def list_lightrag_data_backups() -> list[Path]:
    """Folders under data/backups named lightrag_storage_backup_* with lightrag-en and lightrag-id."""
    root = data_backups_root()
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(root.iterdir(), key=lambda x: x.name):
        if not p.is_dir() or not p.name.startswith("lightrag_storage_backup_"):
            continue
        if (p / "lightrag-en").is_dir() and (p / "lightrag-id").is_dir():
            out.append(p)
    return out


# Default thesis baseline (WikiEval 100 dokumen, README di folder backup).
PREFERRED_DATA_BASELINE_NAME = "lightrag_storage_backup_init_100_context"


def resolve_locale_rag_dir(bundle_root: Path, locale: str) -> Path | None:
    """
    Resolve rag_storage directory for a locale inside a backup bundle.

    Supports:
    - .../lightrag-{en|id}/rag_storage/ (LightRAG/backups layout)
    - .../lightrag-{en|id}/ (flat layout: kv files directly here, data/backups)
    """
    loc = locale.lower()
    if loc not in ("en", "id"):
        raise ValueError("locale must be 'en' or 'id'")
    sub = bundle_root / f"lightrag-{loc}"
    if not sub.is_dir():
        return None
    nested = sub / "rag_storage"
    if (nested / "kv_store_doc_status.json").is_file():
        return nested
    if (sub / "kv_store_doc_status.json").is_file():
        return sub
    return None


def list_before_backup_choices() -> list[tuple[str, Path]]:
    """
    Ordered (label, root) for sidebar. data/backups baselines first, then LightRAG/backups.
    """
    choices: list[tuple[str, Path]] = []
    for p in list_lightrag_data_backups():
        choices.append((f"data/backups/{p.name}", p))
    root = lightrag_backups_root()
    if root.is_dir():
        for p in sorted(root.iterdir(), key=lambda x: x.name):
            if p.is_dir() and not p.name.startswith("."):
                if (p / "lightrag-en").is_dir() or (p / "lightrag-id").is_dir():
                    choices.append((f"LightRAG/backups/{p.name}", p))
    return choices


def default_before_backup_label(choices: list[tuple[str, Path]]) -> str | None:
    if not choices:
        return None
    for label, p in choices:
        if p.name == PREFERRED_DATA_BASELINE_NAME:
            return label
    return choices[0][0]
