"""
Fake Log Router — deterministic SSE replay for UI development and testing.

Endpoint:
  POST /fake/interactive/chat

Replays a pre-defined JSON scenario with realistic delays so the frontend can
iterate on NPC chat rendering without needing a live LLM backend.

Query parameters:
  scenario  — fixture name (default: "basic"). Looks up
              tests/fixtures/fake_scenario_{name}.json
  speed     — float multiplier; >1 = faster, <1 = slower (default: 1.0)

Scenario JSON format (array of event objects):
  [
    {
      "delay_ms": 500,       // pause before emitting this event
      "event": "SUPERVISOR::MULAI",
      "data": { ... }        // arbitrary dict, same shape as real SSE events
    },
    ...
  ]

Auto-resume: HITL events (event starting with "HITL") automatically continue
after `hitl_resume_delay_ms` milliseconds (default: 3000ms / speed).
"""

import asyncio
import json
import os
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger

router = APIRouter()

# Fixtures live under tests/fixtures/ relative to the project root,
# but may also be resolved relative to this file for portability.
_FIXTURES_DIR = (
    Path(__file__).parent.parent.parent.parent.parent  # project root
    / "tests" / "fixtures"
)


def _load_scenario(name: str) -> list:
    fixture_path = _FIXTURES_DIR / f"fake_scenario_{name}.json"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Scenario fixture not found: {fixture_path}")
    with fixture_path.open(encoding="utf-8") as fh:
        return json.load(fh)


async def _replay_stream(
    scenario: str,
    speed: float,
) -> AsyncGenerator[str, None]:
    """Async generator that replays a scenario JSON as SSE events with delays."""
    try:
        events = _load_scenario(scenario)
    except FileNotFoundError as exc:
        yield f"event: WORKFLOW::GALAT\ndata: {json.dumps({'error': str(exc)})}\n\n"
        return
    except json.JSONDecodeError as exc:
        yield f"event: WORKFLOW::GALAT\ndata: {json.dumps({'error': f'Invalid scenario JSON: {exc}' })}\n\n"
        return

    effective_speed = max(0.01, speed)  # guard against zero/negative

    for item in events:
        delay_ms: int = item.get("delay_ms", 0)
        event_name: str = item.get("event", "WORKFLOW::INFO")
        data: dict = item.get("data", {})

        # Wait for the configured delay (scaled by speed)
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000 / effective_speed)

        yield f"event: {event_name}\ndata: {json.dumps(data)}\n\n"

        # Auto-resume HITL events so we don't block the fake stream indefinitely
        if event_name.startswith("HITL"):
            hitl_delay_ms: int = item.get("hitl_resume_delay_ms", 3000)
            logger.debug(f"[FAKE::HITL] Auto-resuming in {hitl_delay_ms / effective_speed:.0f}ms")
            await asyncio.sleep(hitl_delay_ms / 1000 / effective_speed)


@router.post("/interactive/chat")
async def fake_interactive_chat(
    scenario: str = Query(default="basic", description="Scenario fixture name (without prefix/suffix)"),
    speed: float = Query(default=1.0, ge=0.1, le=20.0, description="Playback speed multiplier"),
):
    """
    Replay a fake SSE event stream based on a JSON scenario fixture.

    Useful for developing and testing the NPC chat UI without a live backend.
    Set ENABLE_FAKE_LOGS=true and use this endpoint instead of /api/interactive/chat.
    """
    logger.info(f"[FAKE::REPLAY] scenario={scenario} speed={speed}x")
    return StreamingResponse(
        _replay_stream(scenario=scenario, speed=speed),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
