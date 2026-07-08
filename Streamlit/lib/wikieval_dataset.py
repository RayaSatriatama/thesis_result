"""
WikiEval dataset pipeline ported from notebooks/01_analisis_dataset_wikieval.ipynb.

Loads `dataset/wikiEval_all.json`, validates schema, cleans/deduplicates, and builds
frames for EDA (word counts, question types, context V1 vs V2 similarity).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REQUIRED_COLS = [
    "source",
    "question",
    "answer",
    "context_v1",
    "context_v2",
    "ungrounded_answer",
    "poor_answer",
]


def load_json_robust(path: Path) -> tuple[list[Any], str]:
    encodings = ["utf-8", "utf-8-sig", "latin-1"]
    last_err: Exception | None = None
    for enc in encodings:
        try:
            with open(path, encoding=enc) as f:
                content = f.read().strip()
                if not content:
                    return [], enc
                try:
                    # Try standard JSON array
                    return json.loads(content), enc
                except json.JSONDecodeError:
                    # Fallback to JSONL
                    return [json.loads(line) for line in content.splitlines() if line.strip()], enc
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            last_err = e
            continue
    assert last_err is not None
    raise last_err


def validate_schema(en_data: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    schema_report: list[dict[str, Any]] = []
    for idx, row in enumerate(en_data):
        missing_cols = [c for c in REQUIRED_COLS if c not in row]
        extra_cols = [c for c in row.keys() if c not in REQUIRED_COLS]
        type_issues: list[str] = []
        for c in ("context_v1", "context_v2"):
            if c in row and not isinstance(row[c], (list, str)):
                type_issues.append(f"{c}: {type(row[c]).__name__}")
        schema_report.append(
            {
                "idx": idx,
                "missing_cols": missing_cols,
                "extra_cols": extra_cols,
                "type_issues": type_issues,
            }
        )
    schema_df = pd.DataFrame(schema_report)
    invalid_schema_df = schema_df[
        (schema_df["missing_cols"].apply(len) > 0) | (schema_df["type_issues"].apply(len) > 0)
    ]
    return schema_df, invalid_schema_df


def _clean_text(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def _clean_context(x: Any) -> list[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()]
    if isinstance(x, str):
        s = x.strip()
        return [s] if s else []
    s = str(x).strip()
    return [s] if s else []


@dataclass(frozen=True)
class PreprocessResult:
    cleaned_count: int
    dup_removed: int
    final_count: int
    ringkas_pp: pd.DataFrame


def clean_and_dedup(en_data: list[dict]) -> tuple[list[dict], PreprocessResult]:
    missing_before: list[dict[str, Any]] = []
    cleaned_data: list[dict[str, Any]] = []

    for row in en_data:
        row_clean: dict[str, Any] = {}
        for c in REQUIRED_COLS:
            v = row.get(c, None)
            if c in ("context_v1", "context_v2"):
                row_clean[c] = _clean_context(v)
                is_missing = len(row_clean[c]) == 0
            else:
                row_clean[c] = _clean_text(v)
                is_missing = row_clean[c] == ""
            missing_before.append({"kolom": c, "missing": int(is_missing)})
        cleaned_data.append(row_clean)

    missing_before_df = (
        pd.DataFrame(missing_before)
        .groupby("kolom", as_index=False)["missing"]
        .sum()
        .sort_values("missing", ascending=False)
        .rename(columns={"missing": "missing_sebelum"})
    )

    seen: set[tuple[str, str, str]] = set()
    dedup_data: list[dict[str, Any]] = []
    for row in cleaned_data:
        signature = (
            row["source"].lower(),
            row["question"].lower(),
            row["answer"].lower(),
        )
        if signature not in seen:
            dedup_data.append(row)
            seen.add(signature)

    dup_removed = len(cleaned_data) - len(dedup_data)

    missing_after: list[dict[str, Any]] = []
    for row in dedup_data:
        for c in REQUIRED_COLS:
            if c in ("context_v1", "context_v2"):
                is_missing = len(row[c]) == 0
            else:
                is_missing = row[c] == ""
            missing_after.append({"kolom": c, "missing": int(is_missing)})

    missing_after_df = (
        pd.DataFrame(missing_after)
        .groupby("kolom", as_index=False)["missing"]
        .sum()
        .sort_values("missing", ascending=False)
        .rename(columns={"missing": "missing_sesudah"})
    )

    ringkas_pp = missing_before_df.merge(missing_after_df, on="kolom", how="left")
    stats = PreprocessResult(
        cleaned_count=len(cleaned_data),
        dup_removed=dup_removed,
        final_count=len(dedup_data),
        ringkas_pp=ringkas_pp,
    )
    return dedup_data, stats


def hitung_kata(teks: Any) -> int:
    return len(str(teks).split())


def teks_konteks(ctx: Any) -> str:
    return " ".join(ctx) if isinstance(ctx, list) else str(ctx)


def build_df_src(en_data: list[dict]) -> pd.DataFrame:
    df_src = pd.DataFrame(
        {
            "sumber": [d.get("source", "") for d in en_data],
            "kata_tanya": [hitung_kata(d["question"]) for d in en_data],
            "kata_jawab": [hitung_kata(d["answer"]) for d in en_data],
            "kata_ctx_v1": [hitung_kata(teks_konteks(d["context_v1"])) for d in en_data],
            "kata_ctx_v2": [hitung_kata(teks_konteks(d["context_v2"])) for d in en_data],
            "kata_ungrounded": [hitung_kata(d.get("ungrounded_answer", "")) for d in en_data],
            "kata_buruk": [hitung_kata(d.get("poor_answer", "")) for d in en_data],
        }
    )
    df_src["selisih_ctx"] = df_src["kata_ctx_v2"] - df_src["kata_ctx_v1"]
    df_src["rasio_ctx"] = (df_src["kata_ctx_v2"] / df_src["kata_ctx_v1"]).replace(
        [np.inf, -np.inf], np.nan
    ).round(2)
    return df_src


def build_question_types_df(en_data: list[dict]) -> pd.DataFrame:
    q_types: dict[str, int] = {
        "Apa (What)": 0,
        "Kapan (When)": 0,
        "Di mana (Where)": 0,
        "Bagaimana (How)": 0,
        "Mengapa (Why)": 0,
        "Siapa (Who)": 0,
        "Lainnya": 0,
    }
    for d in en_data:
        q = str(d.get("question", "")).lower().split()
        if "what" in q[:5]:
            q_types["Apa (What)"] += 1
        elif "when" in q[:5]:
            q_types["Kapan (When)"] += 1
        elif "where" in q[:5]:
            q_types["Di mana (Where)"] += 1
        elif "how" in q[:5]:
            q_types["Bagaimana (How)"] += 1
        elif "why" in q[:5]:
            q_types["Mengapa (Why)"] += 1
        elif "who" in q[:5]:
            q_types["Siapa (Who)"] += 1
        else:
            q_types["Lainnya"] += 1
    types_df = pd.DataFrame(list(q_types.items()), columns=["Tipe", "Jumlah"]).sort_values("Jumlah")
    return types_df


def _to_text_context(ctx: Any) -> str:
    if isinstance(ctx, list):
        return " ".join(str(x) for x in ctx)
    return str(ctx)


def _normalize_for_similarity(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _token_counter(text: str) -> tuple[Counter, set[str]]:
    tokens = _normalize_for_similarity(text).split()
    return Counter(tokens), set(tokens)


def _cosine_counter(counter_a: Counter, counter_b: Counter) -> float:
    if not counter_a or not counter_b:
        return 0.0
    common = set(counter_a.keys()) & set(counter_b.keys())
    dot = sum(counter_a[t] * counter_b[t] for t in common)
    norm_a = sqrt(sum(v * v for v in counter_a.values()))
    norm_b = sqrt(sum(v * v for v in counter_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def build_similarity_df(en_data: list[dict]) -> pd.DataFrame:
    similarity_rows: list[dict[str, Any]] = []
    for i, item in enumerate(en_data):
        ctx1_text = _to_text_context(item.get("context_v1", []))
        ctx2_text = _to_text_context(item.get("context_v2", []))

        counter_1, set_1 = _token_counter(ctx1_text)
        counter_2, set_2 = _token_counter(ctx2_text)

        sim_kosinus = _cosine_counter(counter_1, counter_2)
        sim_jaccard = _jaccard_similarity(set_1, set_2)

        panjang_ctx_v1 = len(ctx1_text.split())
        panjang_ctx_v2 = len(ctx2_text.split())

        similarity_rows.append(
            {
                "index_item": i,
                "source": item.get("source", ""),
                "question": item.get("question", ""),
                "sim_kosinus": sim_kosinus,
                "sim_jaccard": sim_jaccard,
                "panjang_ctx_v1": panjang_ctx_v1,
                "panjang_ctx_v2": panjang_ctx_v2,
                "delta_panjang": panjang_ctx_v2 - panjang_ctx_v1,
            }
        )

    df_sim = pd.DataFrame(similarity_rows)
    if df_sim.empty:
        return df_sim
    df_sim["rasio_panjang_v2_v1"] = np.where(
        df_sim["panjang_ctx_v1"] > 0,
        df_sim["panjang_ctx_v2"] / df_sim["panjang_ctx_v1"],
        np.nan,
    )
    return df_sim


@dataclass(frozen=True)
class WikiEvalState:
    """Hasil penuh EDA WikiEval (setara alur notebook 01)."""

    json_path: Path
    encoding: str
    raw_count: int
    schema_df: pd.DataFrame
    invalid_schema_df: pd.DataFrame
    preprocess: PreprocessResult
    en_data: list[dict]
    df_src: pd.DataFrame
    types_df: pd.DataFrame
    df_sim: pd.DataFrame


def build_wikieval_state(json_path: Path) -> tuple[WikiEvalState | None, str | None]:
    if not json_path.is_file():
        return None, f"Berkas tidak ditemukan: {json_path}"
    try:
        en_data, enc = load_json_robust(json_path)
    except Exception as e:
        return None, f"Gagal memuat JSON: {e}"
    if not isinstance(en_data, list):
        return None, "JSON harus berupa array objek."
    raw_count = len(en_data)
    schema_df, invalid_schema_df = validate_schema(en_data)
    en_clean, preprocess = clean_and_dedup(en_data)
    df_src = build_df_src(en_clean)
    types_df = build_question_types_df(en_clean)
    df_sim = build_similarity_df(en_clean)
    state = WikiEvalState(
        json_path=json_path,
        encoding=enc,
        raw_count=raw_count,
        schema_df=schema_df,
        invalid_schema_df=invalid_schema_df,
        preprocess=preprocess,
        en_data=en_clean,
        df_src=df_src,
        types_df=types_df,
        df_sim=df_sim,
    )
    return state, None
