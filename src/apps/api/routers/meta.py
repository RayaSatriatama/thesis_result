"""
Meta endpoints for Story Studio UI (Claw3D fork) — agent list and NPC roster without OpenClaw.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter

from ..npc_registry import list_unique_npc_personas

router = APIRouter()


def _studio_agent_rows() -> List[Dict[str, Any]]:
    """Build `agents.list`-shaped rows from unique NPC personas."""
    rows: List[Dict[str, Any]] = []
    for meta in list_unique_npc_personas():
        aid = str(meta.get("id") or "npc")
        name = str(meta.get("name") or aid)
        rows.append(
            {
                "id": aid,
                "name": name,
                "identity": {
                    "name": name,
                    "theme": meta.get("color"),
                    "emoji": None,
                    "avatar": meta.get("avatar"),
                },
            }
        )
    return rows


@router.get("/studio-agents")
async def list_studio_agents():
    """
    Shape compatible with Claw3D `agents.list` hydration (defaultId, mainKey, agents[]).
    Primary chat agent uses id `story-default`; NPC personas are listed for office presence.
    """
    npc_rows = _studio_agent_rows()
    agents: List[Dict[str, Any]] = [
        {
            "id": "story-default",
            "name": "Story workspace",
            "identity": {
                "name": "Story workspace",
                "theme": "#58a6ff",
                "emoji": "📖",
                "avatar": "story",
            },
        },
        *npc_rows,
    ]
    return {
        "defaultId": "story-default",
        "mainKey": "main",
        "agents": agents,
    }


@router.get("/npcs")
async def list_npcs_raw():
    """Flat NPC list for debugging or alternate UIs."""
    return {"npcs": _studio_agent_rows()}
