"""RAGAS evaluation (Answer Relevancy + Context Relevance) and
FABLES faithfulness metric (Kim et al., 2024; arXiv:2404.01261v2).
"""
import asyncio
import math
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from loguru import logger

from .models import (
    RagasMetricInput,
    RagasMetricOutput,
    FablesExtractInput,
    FablesExtractOutput,
    FablesVerifyInput,
    FablesVerifyOutput,
)

# Claim-level labels aligned with Kim et al. §2 (human annotation scheme).
FABLES_FAITHFUL = "FAITHFUL"
FABLES_UNFAITHFUL = "UNFAITHFUL"
FABLES_PARTIAL_SUPPORT = "PARTIAL_SUPPORT"
FABLES_CANT_VERIFY = "CANT_VERIFY"
EVALUATION_TIMEOUT_SECONDS = 1800


def _epoch_wall_iso_ms(t: float) -> str:
    """UTC ISO-8601 with ms for Langfuse ingestion (wall clock when no export timeline)."""
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _fables_times_for_replay(
    export_timeline: Optional[Dict[str, Dict[str, str]]],
    name: str,
    wall_t0: float,
    wall_t1: float,
) -> Tuple[str, str]:
    """Resolve Langfuse start/end for FABLES replay.

    When ``export_timeline`` is set, **never** uses wall clock at ``wall_t1`` (finish time),
    which would merge with an old immutable ClickHouse ``start_time`` and stretch the trace.
    Falls back across observation names, then a single instant at ``wall_t0``.
    Without export, uses wall clock for both endpoints.
    """

    def _pair_from_block(block: Dict[str, str]) -> Optional[Tuple[str, str]]:
        s = (block.get("start") or "").strip()
        e = (block.get("end") or "").strip()
        if s and e:
            return (s, e) if s <= e else (e, s)
        if s:
            return s, s
        return None

    if export_timeline:
        for key in (
            name,
            "fables_faithfulness",
            "fables_extract_claims",
            "fables_verify_all_claims",
        ):
            block = export_timeline.get(key)
            if not isinstance(block, dict):
                continue
            got = _pair_from_block(block)
            if got:
                return got
        anchor = _epoch_wall_iso_ms(wall_t0)
        return anchor, anchor

    return _epoch_wall_iso_ms(wall_t0), _epoch_wall_iso_ms(wall_t1)


_VALID_FABLES_VERDICTS = frozenset(
    {
        FABLES_FAITHFUL,
        FABLES_UNFAITHFUL,
        FABLES_PARTIAL_SUPPORT,
        FABLES_CANT_VERIFY,
    }
)

try:
    from ragas.metrics.collections import AnswerRelevancy, ContextRelevance
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False


def _parse_fables_verdict_llm(raw: str) -> str:
    """Map free-form LLM output to a single FABLES verdict token."""
    text = (raw or "").strip()
    if not text:
        return FABLES_CANT_VERIFY
    upper = text.upper()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    tail = lines[-1].upper() if lines else upper

    def _pick(chunk_u: str) -> Optional[str]:
        if re.search(r"\bUNFAITHFUL\b", chunk_u) or re.search(r"\bFALSE\b", chunk_u):
            return FABLES_UNFAITHFUL
        if "PARTIAL_SUPPORT" in chunk_u.replace(" ", "") or re.search(
            r"\bPARTIAL\b", chunk_u
        ):
            return FABLES_PARTIAL_SUPPORT
        if (
            "CANT_VERIFY" in chunk_u.replace(" ", "")
            or re.search(r"\bUNVERIFIABLE\b", chunk_u)
            or "CAN'T VERIFY" in chunk_u
            or "CANNOT VERIFY" in chunk_u
        ):
            return FABLES_CANT_VERIFY
        if re.search(r"\bFAITHFUL\b", chunk_u) or re.search(r"\bTRUE\b", chunk_u):
            return FABLES_FAITHFUL
        return None

    for chunk in (tail, upper):
        out = _pick(chunk)
        if out:
            return out
    return FABLES_CANT_VERIFY


class RagasEvaluator:
    """Runs RAGAS (AR + CR) and FABLES faithfulness evaluation via OpenRouter."""

    def __init__(
        self,
        ragas_llm,
        embeddings,
        openai_client,
        model_name: str,
        langfuse,
        openrouter_provider_preferences: Optional[Dict] = None,
    ):
        self._ragas_llm = ragas_llm
        self._ragas_embeddings = embeddings
        self._ragas_openai_client = openai_client
        self._ragas_model_name = model_name
        self.langfuse = langfuse
        self._openrouter_provider_preferences = dict(openrouter_provider_preferences or {})

    def _openrouter_request_kwargs(self) -> Dict:
        """Attach explicit OpenRouter routing only when a caller configured it."""
        if not self._openrouter_provider_preferences:
            return {}
        return {"extra_body": {"provider": self._openrouter_provider_preferences}}

    # -------------------------------------------------------------------------
    # RAGAS (Answer Relevancy + Context Relevance)
    # -------------------------------------------------------------------------

    async def run(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        trace_id: str,
        *,
        fables_replay_only: bool = False,
        fables_recreate_span: bool = False,
        fables_in_place_ids: Optional[Dict[str, str]] = None,
        fables_export_timeline: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> Dict[str, float]:
        """Run Answer Relevancy, Context Relevance, and FABLES faithfulness in parallel.

        When ``fables_replay_only`` is True (Langfuse faithfulness replay tooling), skips
        Answer Relevancy and Context Relevance and does not open ``ragas_evaluation``.
        By default it does **not** create a new ``fables_faithfulness`` span: set Langfuse
        ``trace_context`` with ``parent_span_id`` = existing ``fables_faithfulness`` SPAN.

        If ``fables_recreate_span`` is True (with ``fables_replay_only``), opens a new
        ``fables_faithfulness`` span under ``parent_span_id`` = ``ragas_evaluation`` (replay
        tooling sets this via ``set_faithfulness_replay_trace``).

        If ``fables_in_place_ids`` maps the three FABLES observation names to ids, updates those
        observations in place via ingestion (no new span/generations). Prefer ``--fetch-live``
        so ids match the server.

        ``fables_export_timeline`` (from JSONL/API export): map observation name →
        ``{"start","end"}`` ISO strings so replay keeps the **original** trace timeline instead
        of wall clock.

        FABLES scores are written at **trace** level only (not attached to the span).

        Returns a dict of metric names → float scores.
        """
        if not RAGAS_AVAILABLE:
            return {}

        story_question = "Pembuatan cerita dari teks berikut: " + question

        if fables_replay_only:
            if not self._ragas_openai_client:
                logger.warning("[KRITIK::RAGAS] Replay FABLES: klien OpenAI/OpenRouter tidak tersedia.")
                return {}
            logger.info(
                f"[KRITIK::RAGAS] Replay FABLES saja (tanpa AR/CR), {len(contexts)} konteks sumber."
            )
            ip = dict(fables_in_place_ids or {})
            has_in_place = all(
                (ip.get(k) or "").strip()
                for k in (
                    "fables_faithfulness",
                    "fables_extract_claims",
                    "fables_verify_all_claims",
                )
            )
            if ip and not has_in_place:
                logger.error("[KRITIK::RAGAS] fables_in_place_ids tidak lengkap (perlu 3 nama).")
                return {}
            replay_mode = (not fables_recreate_span) and (not has_in_place)
            return await self._run_fables_faithfulness(
                answer,
                contexts,
                trace_id,
                question=story_question,
                replay_mode=replay_mode,
                fables_recreate_span=fables_recreate_span,
                in_place_observation_ids=ip if has_in_place else None,
                export_timeline=fables_export_timeline,
            )

        if not self._ragas_llm or not self._ragas_embeddings:
            logger.warning(
                "[KRITIK::RAGAS] Model LLM atau embedding belum terinisialisasi, "
                "evaluasi RAGAS dilewati."
            )
            return {}

        logger.info(
            f"[KRITIK::RAGAS] Memulai evaluasi RAGAS secara paralel dengan "
            f"{len(contexts)} konteks sumber."
        )
        start_time = time.time()

        llm = self._ragas_llm
        emb = self._ragas_embeddings

        async def _run_metric(
            name: str,
            coro_factory,
            logged_user_input: str,
            uses_response: bool = True,
        ):
            """Execute one RAGAS metric with up to 3 retries; returns (name, value|None)."""
            for attempt in range(1, 4):
                try:
                    result = await asyncio.wait_for(
                        coro_factory(), timeout=EVALUATION_TIMEOUT_SECONDS
                    )
                    value = result.value if hasattr(result, "value") else float(result)
                    if math.isnan(value):
                        raise ValueError(f"{name} returned NaN")
                    value = round(value, 4)
                    logger.info(f"[KRITIK::RAGAS] Metrik {name} selesai dihitung: {value}")

                    if self.langfuse:
                        self.langfuse.create_score(
                            name=f"ragas_{name}",
                            value=value,
                            trace_id=trace_id,
                            comment=f"RAGAS metric – {name}",
                        )
                        input_payload = RagasMetricInput(
                            metric=name,
                            model=self._ragas_model_name,
                            user_input=logged_user_input,
                            contexts_count=len(contexts),
                            contexts=contexts,
                            response=answer if uses_response else None,
                        )
                        output_payload = RagasMetricOutput(score=value)
                        self.langfuse.log_generation(
                            name=f"ragas_{name}",
                            model=self._ragas_model_name,
                            input_text=input_payload.model_dump_json(indent=2),
                            output_text=output_payload.model_dump_json(indent=2),
                            metadata={"metric": name, "score": value, "trace_id": trace_id},
                        )

                    return (name, value)

                except asyncio.TimeoutError:
                    logger.warning(
                        f"[KRITIK::RAGAS] Metrik {name} melebihi batas waktu "
                        f"{EVALUATION_TIMEOUT_SECONDS}s "
                        f"(percobaan {attempt}/3). "
                        + ("Mencoba ulang..." if attempt < 3 else "Tidak dapat menyelesaikan metrik ini.")
                    )
                    if attempt < 3:
                        await asyncio.sleep(5)
                except Exception as e:
                    wait = attempt * 15
                    logger.warning(
                        f"[KRITIK::RAGAS] Metrik {name} gagal (percobaan {attempt}/3): {e}. "
                        + (f"Mencoba ulang dalam {wait}s..." if attempt < 3 else "Melewati metrik ini.")
                    )
                    if attempt < 3:
                        await asyncio.sleep(wait)

            return (name, None)

        ar = AnswerRelevancy(llm=llm, embeddings=emb, strictness=1)
        cr = ContextRelevance(llm=llm)

        ragas_span_id = None
        if self.langfuse:
            ragas_span_id = self.langfuse.start_span(
                name="ragas_evaluation",
                input_data={
                    "user_input": story_question,
                    "response_length": len(answer),
                    "contexts_count": len(contexts),
                    "note": (
                        "Contexts include [0] planner plan_context + research chunks. "
                        "All metrics use story_question prefix."
                    ),
                },
                metadata={"trace_id": trace_id},
            )

        # NOTE: G-EVAL is NOT part of RAGAS — it runs as a sibling task in CriticAgent.critique()
        results = await asyncio.gather(
            _run_metric(
                "answer_relevancy",
                lambda: ar.ascore(user_input=story_question, response=answer),
                logged_user_input=story_question,
                uses_response=True,
            ),
            _run_metric(
                "context_relevance",
                lambda: cr.ascore(user_input=story_question, retrieved_contexts=contexts),
                logged_user_input=story_question,
                uses_response=False,
            ),
            self._run_fables_faithfulness(answer, contexts, trace_id, question=story_question),
            return_exceptions=False,
        )

        scores = {name: value for name, value in results[:2]}
        fables_dict = results[2] if isinstance(results[2], dict) else {}
        scores.update(fables_dict)

        elapsed = time.time() - start_time
        valid = {k: v for k, v in scores.items() if v is not None}
        logger.success(
            f"[KRITIK::RAGAS] Semua evaluasi RAGAS selesai dalam {elapsed:.1f}s, hasil: {valid}"
        )

        if self.langfuse and ragas_span_id:
            self.langfuse.end_span(
                ragas_span_id,
                output_data={
                    "scores": valid,
                    "elapsed_seconds": round(elapsed, 2),
                    "fables_claims_total": fables_dict.get("fables_claims_total", 0),
                    "fables_claims_faithful": fables_dict.get("fables_claims_faithful", 0),
                    "fables_claims_unfaithful": fables_dict.get("fables_claims_unfaithful", 0),
                    "fables_claims_cant_verify": fables_dict.get("fables_claims_cant_verify", 0),
                    "fables_claims_partial_support": fables_dict.get(
                        "fables_claims_partial_support", 0
                    ),
                },
            )

        return scores

    # -------------------------------------------------------------------------
    # FABLES Faithfulness (Kim et al., 2024; arXiv:2404.01261v2)
    # -------------------------------------------------------------------------

    async def _fables_extract_claims(self, story_text: str) -> List[str]:
        """Extract decontextualized atomic claims from the educational story.

        Mirrors Kim et al. Appendix B / §2: break the text into atomic claims each to be
        checked against evidence (here: konteks riset, including planner + retrieval).
        Each claim must be self-contained (no unresolved pronouns), with temporal,
        locational, and causal context when possible; max 2 sentences; separated with '- '.
        Educational adaptation: strip narrative framing; keep verifiable real-world content.
        """
        if not self._ragas_openai_client:
            return []

        prompt = (
            "You are verifying the faithfulness of statements in an educational story against "
            "the research context that will be provided in the next step."
            "Break the story into atomic claims that will be verified individually later.\n\n"
            "Task: extract ALL statements from the story about the real world that can "
            "be evaluated as true/false against the research material (not a book summary, but "
            "the principle is the same: one claim = one verifiable statement).\n\n"
            "What to extract:\n"
            "- Scientific facts, phenomena, processes; educational concepts; historical facts; real entity properties\n"
            "- Real-world claims even if spoken by fictional characters\n\n"
            "Requirements (per Appendix B / §2):\n"
            "1. Each claim must be fully understandable without other context from the story: "
            "replace pronouns with clear entity names.\n"
            "2. Place claims in their temporal, locational, or causal context when possible.\n"
            "3. Maximum 2 sentences per claim.\n"
            "4. Separate claims with a '- ' prefix on a new line.\n\n"
            "SKIP purely fictional events with no factual real-world content.\n"
            "If there are no verifiable claims: reply exactly with: none\n\n"
            f"Educational story:\n{story_text}\n\n"
            "Atomic claims list:"
        )

        try:
            response = await asyncio.wait_for(
                self._ragas_openai_client.chat.completions.create(
                    model=self._ragas_model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=16384,
                    temperature=0.0,
                    **self._openrouter_request_kwargs(),
                ),
                timeout=EVALUATION_TIMEOUT_SECONDS,
            )
            raw = response.choices[0].message.content or ""
            logger.debug(
                f"[KRITIK::FABLES] Respons ekstraksi klaim diterima ({len(raw)} karakter)."
            )

            raw_lower = raw.strip().lower()
            if raw_lower in ("none", "tidak ada", "tidak ada klaim", "no claims") or raw_lower.startswith("tidak ada klaim") or raw_lower.startswith("there are no"):
                logger.info("[KRITIK::FABLES] LLM menyatakan tidak ada klaim faktual dalam cerita.")
                return []

            claims: List[str] = []

            # Pass 1: bullet lines
            for line in raw.splitlines():
                stripped = line.strip()
                if stripped and stripped[0] in ('-', '\u2013', '\u2014', '*'):
                    claim = stripped.lstrip('-\u2013\u2014* ').strip()
                    if len(claim) > 10:
                        claims.append(claim)

            # Pass 2: numbered list
            if not claims:
                for line in raw.splitlines():
                    m = re.match(r'^\s*\d+[.)\s]\s+(.+)', line)
                    if m:
                        claim = m.group(1).strip()
                        if len(claim) > 10:
                            claims.append(claim)

            # Pass 3: fallback — non-empty sentence-like lines
            if not claims:
                for line in raw.splitlines():
                    line = line.strip()
                    if len(line) > 20 and not line.endswith(':') and line.lower() != "none":
                        claims.append(line)

            logger.info(
                f"[KRITIK::FABLES] Berhasil mengekstrak {len(claims)} klaim faktual dari cerita."
            )
            return claims

        except asyncio.TimeoutError:
            logger.warning(
                "[KRITIK::FABLES] Ekstraksi klaim melebihi batas waktu "
                f"({EVALUATION_TIMEOUT_SECONDS} detik)."
            )
            return []
        except Exception as e:
            logger.warning(f"[KRITIK::FABLES] Ekstraksi klaim gagal: {e}")
            return []

    async def _fables_verify_claim(self, claim: str, context: str) -> str:
        """Verify one atomic claim against context (Kim et al. §2 label scheme).

        Returns one of: FAITHFUL, UNFAITHFUL, PARTIAL_SUPPORT, CANT_VERIFY.
        """
        if not self._ragas_openai_client:
            return FABLES_CANT_VERIFY

        prompt = (
            "You are provided with a research context (including planner snippets if any) and "
            "a single claim from an educational story. Your task: assign ONE faithfulness label "
            "according to the human annotation scheme by Kim et al. (FABLES, §2, arXiv:2404.01261v2).\n\n"
            "LABELS (use exactly one token on the very last line of your response):\n"
            "- FAITHFUL — the claim accurately reflects the narrative/facts supported by the context.\n"
            "- UNFAITHFUL — the claim misrepresents or contradicts the context.\n"
            "- PARTIAL_SUPPORT — partially supported by context, partially missing or extending "
            "beyond what is written (subtle embellishment).\n"
            "- CANT_VERIFY — context provides insufficient evidence to support or refute; "
            "topic is not covered or ambiguous (not automatically false).\n\n"
            "Provide a brief reasoning (1–2 sentences), then the last line must only be the token: "
            "FAITHFUL or UNFAITHFUL or PARTIAL_SUPPORT or CANT_VERIFY\n\n"
            f"Research context:\n{context}\n\n"
            f"Claim:\n{claim}\n\n"
            "Answer:"
        )

        try:
            response = await asyncio.wait_for(
                self._ragas_openai_client.chat.completions.create(
                    model=self._ragas_model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=256,
                    temperature=0.0,
                    **self._openrouter_request_kwargs(),
                ),
                timeout=EVALUATION_TIMEOUT_SECONDS,
            )
            raw = response.choices[0].message.content or ""
            return _parse_fables_verdict_llm(raw)

        except asyncio.TimeoutError:
            logger.warning(
                "[KRITIK::FABLES] Verifikasi klaim melebihi batas waktu "
                f"({EVALUATION_TIMEOUT_SECONDS} detik)."
            )
            return FABLES_CANT_VERIFY
        except Exception as e:
            logger.warning(f"[KRITIK::FABLES] Verifikasi klaim gagal: {e}")
            return FABLES_CANT_VERIFY

    async def _run_fables_faithfulness(
        self,
        answer: str,
        contexts: List[str],
        trace_id: str,
        question: str = "",
        *,
        replay_mode: bool = False,
        fables_recreate_span: bool = False,
        in_place_observation_ids: Optional[Dict[str, str]] = None,
        export_timeline: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> Dict:
        """Run FABLES faithfulness: extract atomic claims, verify each against contexts.

        Kim et al. §4: aggregate on Faithful vs Unfaithful only; Partial support and
        Can't verify are excluded from the FABLES ratio denominator.

        Strict companion score: faithful_count / total_claims (only FAITHFUL counts
        toward the numerator; all other labels lower the ratio).

        ``replay_mode``: do not create a new ``fables_faithfulness`` span; log generations
        under the existing parent (via Langfuse ``trace_context``).
        """
        if not self._ragas_openai_client:
            return {}

        fables_start = time.time()
        score = 0.0
        score_strict = 0.0
        total = faithful = unfaithful = cant_verify = partial_support = 0

        def _usage_from_strings(inp: str, out: str) -> Dict[str, int]:
            i_t = max(1, len(inp) // 4)
            o_t = max(1, len(out) // 4)
            return {"input": i_t, "output": o_t, "total": i_t + o_t}

        ip_ids = in_place_observation_ids or {}
        used_in_place_updates = bool(
            ip_ids.get("fables_faithfulness")
            and ip_ids.get("fables_extract_claims")
            and ip_ids.get("fables_verify_all_claims")
        )
        extract_oid = (ip_ids.get("fables_extract_claims") or "").strip()
        verify_oid = (ip_ids.get("fables_verify_all_claims") or "").strip()

        fables_span_id = None
        used_ingestion_fables_span = False
        span_input = {
            "metric": "fables_faithfulness",
            "framework": (
                "FABLES — Faithfulness Annotations for Book-Length Summarization "
                "(Kim et al., 2024; arXiv:2404.01261v2)"
            ),
            "story_length": len(answer),
            "contexts_count": len(contexts),
            "model": self._ragas_model_name,
            "user_input": question,
        }
        if self.langfuse and not replay_mode and not used_in_place_updates:
            if fables_recreate_span:
                sp_open, _ = _fables_times_for_replay(
                    export_timeline, "fables_faithfulness", fables_start, fables_start
                )
                fables_span_id = self.langfuse.faithfulness_fables_span_start_ingestion(
                    trace_id=trace_id,
                    input_data=span_input,
                    metadata={"trace_id": trace_id},
                    start_time_iso=sp_open,
                    end_time_iso=sp_open,
                )
                if not fables_span_id:
                    logger.error(
                        "[KRITIK::FABLES] Tidak bisa membuat span fables_faithfulness "
                        "(ingestion). Cek LANGFUSE_* dan replay context."
                    )
                    return {}
                used_ingestion_fables_span = True
            else:
                fables_span_id = self.langfuse.start_span(
                    name="fables_faithfulness",
                    input_data=span_input,
                    metadata={"trace_id": trace_id},
                )

        if used_in_place_updates:
            fables_span_id = str(ip_ids["fables_faithfulness"]).strip()

        ctx_str = ""
        try:
            ctx_str = "\n\n---\n\n".join(contexts)

            claims = await self._fables_extract_claims(answer)
            t_after_extract = time.time()

            if self.langfuse:
                ext_in = FablesExtractInput(
                    model=self._ragas_model_name,
                    user_input=answer,
                    story_length_chars=len(answer),
                ).model_dump_json(indent=2)
                ext_out = FablesExtractOutput(
                    claims_extracted=len(claims),
                    claims=claims,
                ).model_dump_json(indent=2)
                if used_in_place_updates:
                    ex_s, ex_e = _fables_times_for_replay(
                        export_timeline,
                        "fables_extract_claims",
                        fables_start,
                        t_after_extract,
                    )
                    self.langfuse.faithfulness_ingestion_generation_update(
                        trace_id=trace_id,
                        observation_id=extract_oid,
                        name="fables_extract_claims",
                        model=self._ragas_model_name,
                        generation_input=ext_in,
                        output_text=ext_out,
                        usage_details=_usage_from_strings(ext_in, ext_out),
                        metadata={"claims_extracted": len(claims), "trace_id": trace_id},
                        start_time=ex_s,
                        end_time=ex_e,
                    )
                else:
                    ex_s, ex_e = _fables_times_for_replay(
                        export_timeline,
                        "fables_extract_claims",
                        fables_start,
                        t_after_extract,
                    )
                    self.langfuse.log_generation(
                        name="fables_extract_claims",
                        model=self._ragas_model_name,
                        input_text=ext_in,
                        output_text=ext_out,
                        metadata={"claims_extracted": len(claims), "trace_id": trace_id},
                        start_time_iso=ex_s,
                        end_time_iso=ex_e,
                    )

            if not claims:
                logger.warning(
                    "[KRITIK::FABLES] Tidak ada klaim faktual yang berhasil diekstrak, "
                    "skor faithfulness ditetapkan None."
                )
                if self.langfuse and used_in_place_updates:
                    vz_in = FablesVerifyInput(
                        model=self._ragas_model_name,
                        user_input=answer,
                        total_claims=0,
                        claims=[],
                        context_chars=len(ctx_str),
                        contexts=list(contexts),
                    ).model_dump_json(indent=2)
                    vz_out = FablesVerifyOutput(
                        faithful=0,
                        unfaithful=0,
                        partial_support=0,
                        cant_verify=0,
                        verdicts=[],
                        summary={
                            "faithful": 0,
                            "unfaithful": 0,
                            "partial_support": 0,
                            "cant_verify": 0,
                        },
                    ).model_dump_json(indent=2)
                    t_after_empty_verify = time.time()
                    vz_s, vz_e = _fables_times_for_replay(
                        export_timeline,
                        "fables_verify_all_claims",
                        t_after_extract,
                        t_after_empty_verify,
                    )
                    self.langfuse.faithfulness_ingestion_generation_update(
                        trace_id=trace_id,
                        observation_id=verify_oid,
                        name="fables_verify_all_claims",
                        model=self._ragas_model_name,
                        generation_input=vz_in,
                        output_text=vz_out,
                        usage_details=_usage_from_strings(vz_in, vz_out),
                        metadata={
                            "total_claims": 0,
                            "trace_id": trace_id,
                        },
                        start_time=vz_s,
                        end_time=vz_e,
                    )
                return {
                    "fables_faithfulness": None,
                    "ragas_standard_faithfulness": None,
                    "fables_claims_total": 0,
                    "fables_claims_faithful": 0,
                    "fables_claims_unfaithful": 0,
                    "fables_claims_cant_verify": 0,
                    "fables_claims_partial_support": 0,
                }

            # Cap at 10 claims — beyond this, cost/latency grows without meaningful gain
            # for short educational stories. Kim et al. verify one claim at a time in the
            # paper; parallel gather here is an engineering choice.
            MAX_CLAIMS = 10
            if len(claims) > MAX_CLAIMS:
                logger.info(
                    f"[KRITIK::FABLES] {len(claims)} klaim ditemukan, dibatasi {MAX_CLAIMS} klaim teratas."
                )
                claims = claims[:MAX_CLAIMS]

            all_results = await asyncio.gather(
                *[self._fables_verify_claim(c, ctx_str) for c in claims],
                return_exceptions=False,
            )
            t_after_verify = time.time()
            verdicts: List[str] = [
                v if v in _VALID_FABLES_VERDICTS else FABLES_CANT_VERIFY
                for v in all_results
            ]

            if self.langfuse:
                verdicts_list = [
                    {"claim": claims[j], "verdict": v} for j, v in enumerate(verdicts)
                ]
                n_faithful = sum(1 for v in verdicts if v == FABLES_FAITHFUL)
                n_unfaithful = sum(1 for v in verdicts if v == FABLES_UNFAITHFUL)
                n_partial = sum(1 for v in verdicts if v == FABLES_PARTIAL_SUPPORT)
                n_cant_verify = sum(1 for v in verdicts if v == FABLES_CANT_VERIFY)
                vz_in = FablesVerifyInput(
                    model=self._ragas_model_name,
                    user_input=answer,
                    total_claims=len(claims),
                    claims=claims,
                    context_chars=len(ctx_str),
                    contexts=list(contexts),
                ).model_dump_json(indent=2)
                vz_out = FablesVerifyOutput(
                    faithful=n_faithful,
                    unfaithful=n_unfaithful,
                    partial_support=n_partial,
                    cant_verify=n_cant_verify,
                    verdicts=verdicts_list,
                    summary={
                        "faithful": n_faithful,
                        "unfaithful": n_unfaithful,
                        "partial_support": n_partial,
                        "cant_verify": n_cant_verify,
                    },
                ).model_dump_json(indent=2)
                if used_in_place_updates:
                    vz_s, vz_e = _fables_times_for_replay(
                        export_timeline,
                        "fables_verify_all_claims",
                        t_after_extract,
                        t_after_verify,
                    )
                    self.langfuse.faithfulness_ingestion_generation_update(
                        trace_id=trace_id,
                        observation_id=verify_oid,
                        name="fables_verify_all_claims",
                        model=self._ragas_model_name,
                        generation_input=vz_in,
                        output_text=vz_out,
                        usage_details=_usage_from_strings(vz_in, vz_out),
                        metadata={
                            "total_claims": len(claims),
                            "faithful": n_faithful,
                            "unfaithful": n_unfaithful,
                            "partial_support": n_partial,
                            "cant_verify": n_cant_verify,
                            "trace_id": trace_id,
                        },
                        start_time=vz_s,
                        end_time=vz_e,
                    )
                else:
                    vz_s, vz_e = _fables_times_for_replay(
                        export_timeline,
                        "fables_verify_all_claims",
                        t_after_extract,
                        t_after_verify,
                    )
                    self.langfuse.log_generation(
                        name="fables_verify_all_claims",
                        model=self._ragas_model_name,
                        input_text=vz_in,
                        output_text=vz_out,
                        metadata={
                            "total_claims": len(claims),
                            "faithful": n_faithful,
                            "unfaithful": n_unfaithful,
                            "partial_support": n_partial,
                            "cant_verify": n_cant_verify,
                            "trace_id": trace_id,
                        },
                        start_time_iso=vz_s,
                        end_time_iso=vz_e,
                    )

            faithful = sum(1 for v in verdicts if v == FABLES_FAITHFUL)
            unfaithful = sum(1 for v in verdicts if v == FABLES_UNFAITHFUL)
            partial_support = sum(1 for v in verdicts if v == FABLES_PARTIAL_SUPPORT)
            cant_verify = sum(1 for v in verdicts if v == FABLES_CANT_VERIFY)
            total = len(verdicts)

            # Kim et al. §4: exclude PARTIAL_SUPPORT and CANT_VERIFY from FABLES denominator
            score = round(faithful / max(faithful + unfaithful, 1), 4)

            # Strict: only FAITHFUL counts in numerator; all other labels count in denominator only
            score_strict = round(faithful / max(total, 1), 4)

            elapsed = time.time() - fables_start

            logger.info(
                f"[KRITIK::FABLES] Evaluasi faithfulness selesai — "
                f"FABLES: {score:.4f} | strict: {score_strict:.4f} "
                f"(faithful={faithful}, unfaithful={unfaithful}, partial={partial_support}, "
                f"cant_verify={cant_verify}, total={total}, {elapsed:.1f}s)"
            )

            if self.langfuse:
                denom_fb = faithful + unfaithful
                # Trace-level scores only (avoid badges on the fables_faithfulness span).
                self.langfuse.create_score(
                    name="fables_faithfulness",
                    value=score,
                    trace_id=trace_id,
                    observation_id=None,
                    comment=(
                        f"FABLES (Kim et al. §4): {faithful}/{denom_fb} "
                        f"on Faithful+Unfaithful only; excluded partial={partial_support}, "
                        f"cant_verify={cant_verify}"
                    ),
                    metadata={
                        "faithful": faithful,
                        "unfaithful": unfaithful,
                        "partial_support": partial_support,
                        "cant_verify": cant_verify,
                        "total_claims": total,
                    },
                )
                self.langfuse.create_score(
                    name="ragas_standard_faithfulness",
                    value=score_strict,
                    trace_id=trace_id,
                    observation_id=None,
                    comment=(
                        f"Strict faithfulness ratio: {faithful}/{total} "
                        f"(only FAITHFUL in numerator)"
                    ),
                    metadata={
                        "faithful": faithful,
                        "non_faithful": total - faithful,
                        "partial_support": partial_support,
                        "cant_verify": cant_verify,
                        "unfaithful": unfaithful,
                        "total_claims": total,
                    },
                )

            return {
                "fables_faithfulness": score,
                "ragas_standard_faithfulness": score_strict,
                "fables_claims_total": total,
                "fables_claims_faithful": faithful,
                "fables_claims_unfaithful": unfaithful,
                "fables_claims_cant_verify": cant_verify,
                "fables_claims_partial_support": partial_support,
            }

        finally:
            if self.langfuse and fables_span_id:
                out_payload = {
                    "fables_faithfulness": score,
                    "ragas_standard_faithfulness": score_strict,
                    "fables_claims_total": total,
                    "fables_claims_faithful": faithful,
                    "fables_claims_unfaithful": unfaithful,
                    "fables_claims_cant_verify": cant_verify,
                    "fables_claims_partial_support": partial_support,
                    "chars": {"input_chars": len(answer) + len(ctx_str)},
                    "elapsed_seconds": round(time.time() - fables_start, 2),
                }
                if used_in_place_updates:
                    t_span_end = time.time()
                    sp_s, sp_e = _fables_times_for_replay(
                        export_timeline,
                        "fables_faithfulness",
                        fables_start,
                        t_span_end,
                    )
                    self.langfuse.faithfulness_ingestion_span_update_output(
                        trace_id=trace_id,
                        observation_id=str(fables_span_id),
                        output_data=out_payload,
                        start_time=sp_s,
                        end_time=sp_e,
                    )
                elif used_ingestion_fables_span:
                    t_span_end = time.time()
                    sp_s, sp_e = _fables_times_for_replay(
                        export_timeline,
                        "fables_faithfulness",
                        fables_start,
                        t_span_end,
                    )
                    self.langfuse.faithfulness_fables_span_end_ingestion(
                        trace_id=trace_id,
                        observation_id=fables_span_id,
                        output_data=out_payload,
                        start_time_iso=sp_s,
                        end_time_iso=sp_e,
                    )
                else:
                    self.langfuse.end_span(fables_span_id, output_data=out_payload)
