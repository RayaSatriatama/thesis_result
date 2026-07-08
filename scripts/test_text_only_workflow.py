"""
Test full workflow with text-only (no image, no diagram).
Verifies SCORE Langfuse finalization scoring.
"""
import asyncio
import os
import sys
from loguru import logger

# Add project root and src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from src.workflows.story_agent.graph import create_story_workflow


async def run_test():
    logger.info("Initializing Story Agent Workflow (Text Only)...")
    graph = create_story_workflow()

    input_payload = {
        "user_message": "Buat cerita dari materi ini",
        "learning_objectives": "Pengenalan Kecerdasan Artifisial",
        "target_age": "10-12",
        "theme": "Kecerdasan Artifisial",
        "enriched_context": """
        [Learning Context]
        Modul: test data
        Bagian: Pengenalan Kecerdasan Artifisial

        [Exercise Details]
        Jenis: Kelompokkan
        Prompt: Drag item-item berikut ke bucket yang benar: Bebek atau Ayam.
        Items: Bebek1, Ayam2, Bebek3, Ayam4
        Kategori: Bebek, Ayam
        """,
        "language": "Indonesian",
        "story_length": "short",
        "story_style": "adventure",
        "narrative_style": "dialog_dominan",
        "emotional_tone": "exciting",
        "active_writers": ["text"],  # Text only - no image, no diagram
    }

    print("-" * 50)
    print("Starting Workflow (Text Only, No Image/Diagram)")
    msg = input_payload["user_message"]
    print(f"User Message: {msg}")
    print("-" * 50)

    result = await graph.ainvoke(input_payload)

    print("\n" + "=" * 50)
    print("WORKFLOW COMPLETED")
    print("=" * 50)

    title = result.get("draft_title", "No Title")
    print(f"Title: {title}")

    story = result.get("final_story", "No Story Generated")
    if len(story) > 500:
        print(f"Final Story:\n{story[:500]}...\n[truncated]")
    else:
        print(f"Final Story:\n{story}")

    score = result.get("quality_score", "N/A")
    print(f"\nQuality Score: {score}/10")

    critique = str(result.get("critique_feedback", "N/A"))
    if len(critique) > 200:
        print(f"Critique Feedback: {critique[:200]}...")
    else:
        print(f"Critique Feedback: {critique}")


if __name__ == "__main__":
    asyncio.run(run_test())
