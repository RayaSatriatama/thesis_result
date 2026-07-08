import asyncio
import os
import sys
from loguru import logger

# Add project root and src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from src.workflows.story_agent.graph import create_story_workflow
from src.workflows.story_agent.state import StoryState

async def run_test():
    """
    Run full workflow with specific user prompt and context
    """
    logger.info("Initializing Story Agent Workflow...")
    
    # Initialize graph
    graph = create_story_workflow()
    
    # Define input payload based on User Request
    input_payload = {
        "user_message": "Buat cerita dari materi ini sediakan diagram dan gambar",
        "learning_objectives": "Pengenalan Kecerdasan Artifisial",
        "target_age": "10-12",  # Defaulting to a reasonable age range if not specified
        "theme": "Kecerdasan Artifisial",
        # Enriched context combining Modul, Bagian, and Exercise Details
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
        # Default settings
        "language": "Indonesian",
        "story_length": "short",
        "story_style": "adventure",
        "narrative_style": "dialog_dominan",
        "emotional_tone": "exciting",
        "active_writers": ["text", "diagram", "image"] # Enable all writers
    }
    
    print("-" * 50)
    print("Starting Workflow with Custom Input:")
    print(f"User Message: {input_payload['user_message']}")
    print(f"Context: {input_payload['enriched_context'][:100]}...")
    print("-" * 50)

    # Run workflow
    result = await graph.ainvoke(input_payload)
    
    print("\n" + "=" * 50)
    print("WORKFLOW COMPLETED")
    print("=" * 50)
    
    # Print Results
    print(f"Title: {result.get('draft_title', 'No Title')}")
    print(f"Final Story:\n{result.get('final_story', 'No Story Generated')[:500]}...\n[truncated]")
    
    # Check Diagram
    if result.get('draft_diagram'):
        print(f"\n[Diagram Generated]: Yes\nTitle: {result.get('diagram_title')}")
        print(f"Code: {result.get('draft_diagram')[:50]}...")
    else:
        print("\n[Diagram Generated]: No")
        
    # Check Images
    if result.get('generated_images'):
        print(f"\n[Images Generated]: {len(result.get('generated_images'))}")
        for img in result.get('generated_images'):
            print(f"- {img.get('prompt', '')[:50]}...")
    else:
         print("\n[Images Generated]: No")

    # Check Score
    print(f"\nQuality Score: {result.get('quality_score')}/10")
    print(f"Critique Feedback: {result.get('critique_feedback')[:100]}...")

if __name__ == "__main__":
    asyncio.run(run_test())
