"""Aggregate metrics from LightRAG kv_store_doc_status.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RagStorageStats:
    total_docs: int
    wikieval_v1: int
    wikieval_v2: int
    wikieval_total: int
    unknown_source: int
    other_docs: int
    total_chunks: int
    source_path: str
    error: str | None = None

    def to_row_dict(self) -> dict[str, Any]:
        return {
            "Total dokumen": self.total_docs,
            "WikiEval v1": self.wikieval_v1,
            "WikiEval v2": self.wikieval_v2,
            "WikiEval total": self.wikieval_total,
            "unknown_source": self.unknown_source,
            "Dokumen lain (non-WikiEval path)": self.other_docs,
            "Total chunks (sum chunks_count)": self.total_chunks,
        }


def _classify_path(file_path: str) -> str:
    fp = file_path or ""
    if fp == "unknown_source" or not fp.strip():
        return "unknown_source"
    if fp.startswith("wikieval/") and fp.endswith("/v1"):
        return "wikieval_v1"
    if fp.startswith("wikieval/") and fp.endswith("/v2"):
        return "wikieval_v2"
    if fp.startswith("wikieval/"):
        return "wikieval_other"
    return "other"


def load_rag_storage_stats(rag_storage_dir: str | Path) -> RagStorageStats:
    path = Path(rag_storage_dir)
    doc_status = path / "kv_store_doc_status.json"
    sp = str(path.resolve())

    if not doc_status.is_file():
        return RagStorageStats(
            total_docs=0,
            wikieval_v1=0,
            wikieval_v2=0,
            wikieval_total=0,
            unknown_source=0,
            other_docs=0,
            total_chunks=0,
            source_path=sp,
            error=f"Missing {doc_status.name}",
        )

    try:
        with open(doc_status, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return RagStorageStats(
            total_docs=0,
            wikieval_v1=0,
            wikieval_v2=0,
            wikieval_total=0,
            unknown_source=0,
            other_docs=0,
            total_chunks=0,
            source_path=sp,
            error=str(e),
        )

    w1 = w2 = w_other = unk = other = 0
    total_chunks = 0
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        fp = str(entry.get("file_path", "") or "")
        bucket = _classify_path(fp)
        if bucket == "wikieval_v1":
            w1 += 1
        elif bucket == "wikieval_v2":
            w2 += 1
        elif bucket == "wikieval_other":
            w_other += 1
        elif bucket == "unknown_source":
            unk += 1
        else:
            other += 1
        cc = entry.get("chunks_count")
        if isinstance(cc, int):
            total_chunks += cc

    w_total = w1 + w2 + w_other

    return RagStorageStats(
        total_docs=len(data),
        wikieval_v1=w1,
        wikieval_v2=w2,
        wikieval_total=w_total,
        unknown_source=unk,
        other_docs=other,
        total_chunks=total_chunks,
        source_path=sp,
        error=None,
    )


# --- Extended KG / VDB / GraphML metrics (for before vs after comparison) ---


@dataclass(frozen=True)
class ExtendedKGStats:
    """Counts from rag_storage JSON + GraphML (LightRAG export layout)."""

    vdb_entities: int
    vdb_relationships: int
    vdb_chunks: int
    kv_full_entities: int
    kv_full_relations: int
    graphml_nodes: int
    graphml_edges: int
    source_path: str
    error: str | None = None

    def to_row_dict(self) -> dict[str, int | str]:
        return {
            "VDB entities (embedding data[])": self.vdb_entities,
            "VDB relationships (data[])": self.vdb_relationships,
            "VDB chunks (data[])": self.vdb_chunks,
            "KV full_entities (keys)": self.kv_full_entities,
            "KV full_relations (keys)": self.kv_full_relations,
            "GraphML nodes (<node id=)": self.graphml_nodes,
            "GraphML edges (<edge source=)": self.graphml_edges,
        }


def _count_substrings_in_file(path: Path, needle: str) -> int:
    n = 0
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(8 * 1024 * 1024)
                if not chunk:
                    break
                n += chunk.decode("utf-8", errors="ignore").count(needle)
    except OSError:
        return -1
    return n


def _json_dict_len(path: Path) -> int:
    if not path.is_file():
        return -1
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return len(data)
    except (OSError, json.JSONDecodeError):
        return -1
    return -1


def _vdb_data_len(path: Path) -> int:
    if not path.is_file():
        return -1
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return -1
        inner = data.get("data")
        if isinstance(inner, list):
            return len(inner)
    except (OSError, json.JSONDecodeError):
        return -1
    return -1


def load_extended_kg_stats(rag_storage_dir: str | Path) -> ExtendedKGStats:
    path = Path(rag_storage_dir)
    sp = str(path.resolve())
    if not path.is_dir():
        return ExtendedKGStats(
            -1, -1, -1, -1, -1, -1, -1, sp, error="Not a directory"
        )

    gml = path / "graph_chunk_entity_relation.graphml"
    nodes = _count_substrings_in_file(gml, '<node id="') if gml.is_file() else -1
    edges = _count_substrings_in_file(gml, '<edge source="') if gml.is_file() else -1

    return ExtendedKGStats(
        vdb_entities=_vdb_data_len(path / "vdb_entities.json"),
        vdb_relationships=_vdb_data_len(path / "vdb_relationships.json"),
        vdb_chunks=_vdb_data_len(path / "vdb_chunks.json"),
        kv_full_entities=_json_dict_len(path / "kv_store_full_entities.json"),
        kv_full_relations=_json_dict_len(path / "kv_store_full_relations.json"),
        graphml_nodes=nodes,
        graphml_edges=edges,
        source_path=sp,
        error=None,
    )


