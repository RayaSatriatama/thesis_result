"""
Faithfulness confusion-matrix metrics for the 10-sample thesis dashboard.

Ground truth: manual false-positive claim indices (hallucinated but judged FAITHFUL)
must match `generate_faithfulness_images_10.py` / `calc_f1.py`.
`FABLES_VERDICT_OVERRIDE` is imported by the HTML generator for the same effective labels.

FABLES (Kim et al. §4): only FAITHFUL vs UNFAITHFUL in the 2×2; CANT_VERIFY and
PARTIAL_SUPPORT excluded from the matrix, kecuali pasangan di ``MANUAL_GT_FAITHFUL``
(verdict tetap PARTIAL_SUPPORT; GT positif → dihitung FN bila pred bukan FAITHFUL).
RAGAS-style display (thesis): pred positive = FAITHFUL only; UNFAITHFUL + PARTIAL_SUPPORT + CANT_VERIFY = negative.
"""

from __future__ import annotations

import glob
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from lib.paths import repo_root


# Sync with generate_faithfulness_images_10.py → hallucinated_claims keys (story_idx 1-based, claim_idx 1-based).
# Cohort Apr 2026 (10 traces dari Eval_Data terbaru): FP = FAITHFUL padahal bukti di luar Rencana Planner tipis/salah retrieval.
MANUAL_HALLUCINATED: dict[int, frozenset[int]] = {
    9: frozenset({1}),
}

# Ground truth manual (kelas positif = faithful terhadap konteks), terpisah dari label prediksi di export.
# Dipakai saat verifikator memilih PARTIAL_SUPPORT / UNFAITHFUL padahal bukti mendukung klaim → FN bila pred tidak FAITHFUL (FABLES) / tidak positif RAGAS-style.
MANUAL_GT_FAITHFUL: dict[int, frozenset[int]] = {
    # Story 4 klaim 8: FABLES melabeli PARTIAL_SUPPORT padahal angka 111 terluka sesuai penuh dengan konteks → FN.
    4: frozenset({8}),
}

# Ganti label FABLES dari export mentah bila audit manual beda (sinkron dengan generate_faithfulness_images_10.py).
FABLES_VERDICT_OVERRIDE: dict[int, dict[int, str]] = {}


def fables_verdict_effective(cerita_idx: int, klaim_idx: int, raw_verdict: str | None) -> str:
    r = (raw_verdict or "UNKNOWN").strip() or "UNKNOWN"
    o = FABLES_VERDICT_OVERRIDE.get(cerita_idx, {}).get(klaim_idx)
    return o if o is not None else r


def _ensure_sampling_path() -> None:
    root = repo_root()
    p = str(root / "scripts" / "sampling")
    if sys.path[0] != p:
        if p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)


def extract_top(df_all: pd.DataFrame, prompt_filter: str) -> pd.DataFrame:
    """Same sampling as generate_faithfulness_images_10.py."""
    df = df_all[df_all["input"].astype(str).str.contains(prompt_filter, na=False)].copy()
    mu = "geval_coherence_raw" if "geval_coherence_raw" in df.columns else "geval_coherence_normalized"
    ms_ragas = "ragas_standard_faithfulness"
    ms_fables = "fables_faithfulness"
    mc = "claims_total_new" if "claims_total_new" in df.columns else None
    subset_cols = [mu, ms_ragas, ms_fables]
    if mc:
        subset_cols.append(mc)
    df_valid = df.dropna(subset=subset_cols).copy()

    s_vals = [ms_fables, ms_ragas, mu]
    df_sorted = df_valid.sort_values(by=s_vals, ascending=[True, True, True], kind="mergesort").copy()

    def pick_two_from_start(df_in: pd.DataFrame) -> pd.DataFrame:
        if df_in.empty:
            return df_in
        first = df_in.iloc[0]
        same = df_in[
            (df_in[ms_fables] == first[ms_fables])
            & (df_in[ms_ragas] == first[ms_ragas])
            & (df_in[mu] == first[mu])
        ]
        if mc and len(same) >= 2:
            a = same.sort_values(by=[mc, "id"], ascending=[True, True]).head(1)
            b = same.sort_values(by=[mc, "id"], ascending=[False, True]).head(1)
            picked = pd.concat([a, b]).drop_duplicates(subset=["id"])
            if len(picked) == 2:
                return picked
        return df_in.head(2)

    def pick_two_from_end(df_in: pd.DataFrame) -> pd.DataFrame:
        if df_in.empty:
            return df_in
        last = df_in.iloc[-1]
        same = df_in[
            (df_in[ms_fables] == last[ms_fables])
            & (df_in[ms_ragas] == last[ms_ragas])
            & (df_in[mu] == last[mu])
        ]
        if mc and len(same) >= 2:
            a = same.sort_values(by=[mc, "id"], ascending=[True, True]).head(1)
            b = same.sort_values(by=[mc, "id"], ascending=[False, True]).head(1)
            picked = pd.concat([a, b]).drop_duplicates(subset=["id"])
            if len(picked) == 2:
                return picked
        return df_in.tail(2)

    min2 = pick_two_from_start(df_sorted).copy()
    min2["kategori"] = "SKOR RENDAH"

    max2 = pick_two_from_end(df_sorted).copy()
    max2["kategori"] = "SKOR TINGGI"

    mid_idx = len(df_sorted) // 2
    s_sedang = df_sorted.iloc[[mid_idx]].copy()
    s_sedang["kategori"] = "SKOR SEDANG"

    return pd.concat([max2, s_sedang, min2])


def load_ten_story_traces_df() -> pd.DataFrame:
    _ensure_sampling_path()
    from sampling_expert import get_latest_trace_df  # noqa: E402

    df_all = get_latest_trace_df()
    
    # Inject GEval raw and total claims from latest observations export
    try:
        root = repo_root()
        obs_dir_for_geval = root / "Eval_Data" / "Observations"
        obs_files_for_geval = sorted(glob.glob(str(obs_dir_for_geval / "*.jsonl")))
        latest_obs_for_geval = obs_files_for_geval[-1] if obs_files_for_geval else None
        if latest_obs_for_geval:
            geval_raw_map: dict[str, float] = {}
            claims_total_map: dict[str, int] = {}
            with open(latest_obs_for_geval, encoding="utf-8") as f_in:
                for line in f_in:
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    tid = str(d.get("traceId") or "").strip()
                    nm = str(d.get("name") or "")
                    out = d.get("output", {})
                    if isinstance(out, str):
                        try:
                            out = json.loads(out)
                        except json.JSONDecodeError:
                            out = {}

                    if nm == "geval_coherence":
                        if isinstance(out, dict) and "geval_coherence" in out:
                            try:
                                geval_raw_map[tid] = float(out["geval_coherence"])
                            except (TypeError, ValueError):
                                continue
                    elif nm.startswith("fables_verify_all_claims"):
                        if isinstance(out, dict) and isinstance(out.get("verdicts"), list):
                            claims_total_map[tid] = claims_total_map.get(tid, 0) + len(out["verdicts"])
            if "id" in df_all.columns and geval_raw_map:
                df_all["geval_coherence_raw"] = df_all["id"].map(geval_raw_map)
            if "id" in df_all.columns and claims_total_map:
                df_all["claims_total_new"] = df_all["id"].map(claims_total_map)
    except Exception:
        pass

    expert_en = extract_top(df_all, "Create an").copy()
    expert_id = extract_top(df_all, "Buat cerita").copy()
    expert_en["lang"] = "en"
    expert_id["lang"] = "id"
    out = pd.concat([expert_en, expert_id], ignore_index=True)
    out["story_idx"] = np.arange(1, len(out) + 1)
    return out


def load_all_traces_df() -> pd.DataFrame:
    """Load the latest exported trace CSV (all rows) via the sampling helper."""
    _ensure_sampling_path()
    from sampling_expert import get_latest_trace_df  # noqa: E402

    return get_latest_trace_df().copy()


def filter_all_traces_by_language(df_all: pd.DataFrame, lang_filter: str) -> pd.DataFrame:
    """
    Filter *all* traces by language convention used in sampling:
    - EN: prompt contains "Create an"
    - ID: prompt contains "Buat cerita"
    """
    lf = (lang_filter or "all").strip().lower()
    if lf in ("", "all", "semua"):
        return df_all
    if lf == "en":
        return df_all[df_all["input"].astype(str).str.contains("Create an", na=False)].copy()
    if lf == "id":
        return df_all[df_all["input"].astype(str).str.contains("Buat cerita", na=False)].copy()
    return df_all


def filter_tops_by_language(tops: pd.DataFrame, lang_filter: str) -> pd.DataFrame:
    """lang_filter: 'all' | 'en' | 'id' (matches HTML naming EN / ID)."""
    lf = (lang_filter or "all").strip().lower()
    if lf in ("", "all", "semua"):
        return tops
    if lf == "en":
        return tops[tops["lang"] == "en"].reset_index(drop=True)
    if lf == "id":
        return tops[tops["lang"] == "id"].reset_index(drop=True)
    return tops


def load_trace_claims(trace_ids: list[Any]) -> dict[str, list[dict[str, Any]]]:
    root = repo_root()
    obs_dir = root / "Eval_Data" / "Observations"
    want = {str(t).strip('"') for t in trace_ids}
    
    # Store temporary lists of base and extra claims per trace
    temp_base: dict[str, list[dict[str, Any]]] = {}
    temp_extra: dict[str, list[dict[str, Any]]] = {}
    
    for f in sorted(glob.glob(str(obs_dir / "*.jsonl"))):
        with open(f, encoding="utf-8") as f_in:
            for line in f_in:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tid = str(obj.get("traceId", "")).strip('"')
                name = str(obj.get("name") or "").strip()
                if not name.startswith("fables_verify_all_claims") or tid not in want:
                    continue
                raw = obj.get("output", {})
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                verdicts = raw.get("verdicts") or []
                verdicts = verdicts if isinstance(verdicts, list) else []
                if not verdicts:
                    continue
                
                if name == "fables_verify_all_claims":
                    if tid not in temp_base:
                        temp_base[tid] = []
                    temp_base[tid].extend(verdicts)
                elif name.startswith("fables_verify_all_claims_"):
                    if tid not in temp_extra:
                        temp_extra[tid] = []
                    temp_extra[tid].extend(verdicts)
                    
    out: dict[str, list[dict[str, Any]]] = {}
    for tid in want:
        base = temp_base.get(tid, [])
        extra = temp_extra.get(tid, [])
        out[tid] = base + extra
        
    return out


def _ground_truth(cerita_idx: int, klaim_idx: int, pred_fables_positive: bool) -> bool:
    if cerita_idx in MANUAL_HALLUCINATED and klaim_idx in MANUAL_HALLUCINATED[cerita_idx]:
        return False
    if cerita_idx in MANUAL_GT_FAITHFUL and klaim_idx in MANUAL_GT_FAITHFUL[cerita_idx]:
        return True
    return pred_fables_positive


@dataclass(frozen=True)
class FaithfulnessBundle:
    tp: int
    fp: int
    tn: int
    fn: int
    n_cant_verify_excluded: int
    n_partial_support_excluded: int
    n_total_claims: int

    @property
    def n_fables_evaluated(self) -> int:
        return self.tp + self.fp + self.tn + self.fn


def compute_bundle_fables(tops: pd.DataFrame, trace_claims: dict[str, list]) -> FaithfulnessBundle:
    tp = fp = tn = fn = 0
    n_cv = 0
    n_ps = 0
    n_total = 0
    for _, row in tops.iterrows():
        cerita_idx = int(row["story_idx"])
        tid = str(row["id"]).strip('"')
        claims = trace_claims.get(tid, [])
        for idx_c, c in enumerate(claims):
            n_total += 1
            klaim_idx = idx_c + 1
            v = fables_verdict_effective(cerita_idx, klaim_idx, c.get("verdict"))
            if v == "CANT_VERIFY":
                n_cv += 1
                continue
            if v == "PARTIAL_SUPPORT":
                if klaim_idx in MANUAL_GT_FAITHFUL.get(cerita_idx, frozenset()):
                    pred_pos = False
                    gt_pos = _ground_truth(cerita_idx, klaim_idx, pred_fables_positive=False)
                    if pred_pos and gt_pos:
                        tp += 1
                    elif pred_pos and not gt_pos:
                        fp += 1
                    elif not pred_pos and not gt_pos:
                        tn += 1
                    else:
                        fn += 1
                else:
                    n_ps += 1
                continue
            pred_pos = v == "FAITHFUL"
            gt_pos = _ground_truth(cerita_idx, klaim_idx, pred_pos)
            if pred_pos and gt_pos:
                tp += 1
            elif pred_pos and not gt_pos:
                fp += 1
            elif not pred_pos and not gt_pos:
                tn += 1
            else:
                fn += 1
    return FaithfulnessBundle(tp, fp, tn, fn, n_cv, n_ps, n_total)


def compute_bundle_ragas(tops: pd.DataFrame, trace_claims: dict[str, list]) -> FaithfulnessBundle:
    """
    All claims in the 2×2. Positive prediction = FAITHFUL only.

    UNFAITHFUL, PARTIAL_SUPPORT, and CANT_VERIFY are treated as negative (pred not faithful),
    aligned with strict trace score ragas_standard_faithfulness (faithful / total).
    """
    tp = fp = tn = fn = n_total = 0
    for _, row in tops.iterrows():
        cerita_idx = int(row["story_idx"])
        tid = str(row["id"]).strip('"')
        claims = trace_claims.get(tid, [])
        for idx_c, c in enumerate(claims):
            n_total += 1
            klaim_idx = idx_c + 1
            v = fables_verdict_effective(cerita_idx, klaim_idx, c.get("verdict"))
            pred_fables = v == "FAITHFUL"
            pred_pos = v == "FAITHFUL"
            gt_pos = _ground_truth(cerita_idx, klaim_idx, pred_fables)
            if pred_pos and gt_pos:
                tp += 1
            elif pred_pos and not gt_pos:
                fp += 1
            elif not pred_pos and not gt_pos:
                tn += 1
            else:
                fn += 1
    return FaithfulnessBundle(tp, fp, tn, fn, 0, 0, n_total)


def _f1(precision: float, recall: float) -> float:
    if precision + recall <= 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def metrics_from_bundle(b: FaithfulnessBundle) -> dict[str, Any]:
    tp, fp, tn, fn = b.tp, b.fp, b.tn, b.fn
    prec_pos = tp / (tp + fp) if (tp + fp) else 0.0
    rec_pos = tp / (tp + fn) if (tp + fn) else 0.0
    f1_pos = _f1(prec_pos, rec_pos)

    prec_neg = tn / (tn + fn) if (tn + fn) else 0.0
    rec_neg = tn / (tn + fp) if (tn + fp) else 0.0
    f1_neg = _f1(prec_neg, rec_neg)

    macro_f1 = (f1_pos + f1_neg) / 2.0
    support_pos = tp + fn
    support_neg = fp + tn
    total = tp + fp + tn + fn
    w_prec = (prec_pos * support_pos + prec_neg * support_neg) / total if total else 0.0
    w_rec = (rec_pos * support_pos + rec_neg * support_neg) / total if total else 0.0
    w_f1 = (f1_pos * support_pos + f1_neg * support_neg) / total if total else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision_faithful": prec_pos,
        "recall_faithful": rec_pos,
        "f1_faithful": f1_pos,
        "precision_unfaithful": prec_neg,
        "recall_unfaithful": rec_neg,
        "f1_unfaithful": f1_neg,
        "macro_f1": macro_f1,
        "weighted_f1": w_f1,
        "weighted_precision": w_prec,
        "weighted_recall": w_rec,
        "support_faithful": support_pos,
        "support_unfaithful": support_neg,
        "n_evaluated": total,
        "n_cant_verify_excluded": b.n_cant_verify_excluded,
        "n_partial_support_excluded": b.n_partial_support_excluded,
        "n_total_claims": b.n_total_claims,
    }


def load_metrics_or_fallback(
    lang_filter: str = "all",
) -> tuple[dict[str, Any], dict[str, Any], bool, pd.DataFrame | None]:
    """
    Returns (fables_metrics, ragas_metrics, used_live_data, filtered_tops_or_none).

    lang_filter: 'all' | 'en' | 'id' — subset jejak (story_idx tetap 1..10) untuk matriks & skor.

    If observations/traces are missing, returns derived constants from the Apr 2026 manual FP set (story 9 klaim 1).
    """
    try:
        tops_full = load_ten_story_traces_df()
        tops = filter_tops_by_language(tops_full, lang_filter)
        if tops.empty:
            raise ValueError("empty tops after language filter")
        ids = tops["id"].tolist()
        tc = load_trace_claims(ids)

        def _empty() -> bool:
            for _, row in tops.iterrows():
                tid = str(row["id"]).strip('"')
                if tc.get(tid):
                    return False
            return True

        if not tc or _empty():
            raise ValueError("empty claims")
        bf = compute_bundle_fables(tops, tc)
        br = compute_bundle_ragas(tops, tc)
        return metrics_from_bundle(bf), metrics_from_bundle(br), True, tops
    except Exception as e:
        import traceback
        print("ERROR IN load_metrics_or_fallback:")
        traceback.print_exc()
        # Fallback: Apr 2026 manual FP map (story 9 klaim 1 only); replace when Observations return.
        bf = FaithfulnessBundle(68, 1, 4, 1, 9, 2, 85)
        br = FaithfulnessBundle(68, 1, 15, 1, 0, 0, 85)
        return metrics_from_bundle(bf), metrics_from_bundle(br), False, None
