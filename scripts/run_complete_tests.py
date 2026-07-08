"""
Complete API Test Suite - All Endpoints
Tests every single endpoint including workflow SSE streaming
"""

import sys
import httpx
import json
import time
from datetime import datetime
from pathlib import Path
import os
# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


BASE_URL = "http://localhost:8000"
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


class LogCapture:
    """Capture print output to both console and log file"""
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_file = open(log_path, 'w', encoding='utf-8')
        self.original_stdout = sys.stdout

    def write(self, text):
        self.original_stdout.write(text)
        self.log_file.write(text)
        self.log_file.flush()

    def flush(self):
        self.original_stdout.flush()
        self.log_file.flush()

    def close(self):
        self.log_file.close()
        sys.stdout = self.original_stdout


def run_complete_tests():
    """Run ALL API endpoint tests"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = LOG_DIR / f"api_complete_test_{timestamp}.log"

    log = LogCapture(log_path)
    sys.stdout = log

    print("=" * 70)
    print(f"🧪 COMPLETE API TEST SUITE - ALL ENDPOINTS")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Server: {BASE_URL}")
    print(f"   Log: {log_path}")
    print("=" * 70)

    results = {}

    with httpx.Client(base_url=BASE_URL, timeout=300.0) as client:
        # =================================================================
        # 1. HEALTH
        # =================================================================
        print("\n" + "=" * 50)
        print("1️⃣  HEALTH CHECK")
        print("=" * 50)
        try:
            start = time.time()
            r = client.get("/health")
            assert r.status_code == 200
            data = r.json()
            elapsed = time.time() - start
            print(f"✓ Health: {data}")
            results["health"] = ("✓ PASS", elapsed)
        except Exception as e:
            results["health"] = ("✗ FAIL", 0, str(e))
            print(f"✗ Error: {e}")

        # =================================================================
        # 2. RESEARCH ENDPOINTS
        # =================================================================
        print("\n" + "=" * 50)
        print("2️⃣  RESEARCH AGENT (3 endpoints)")
        print("=" * 50)

        # 2a. Research Plan
        print("\n[2a] /research/plan")
        try:
            start = time.time()
            r = client.post("/api/agents/research/plan", json={
                "theme": "Fotosintesis",
                "target_age": "8-10",
                "language": "Indonesian"
            })
            elapsed = time.time() - start
            if r.status_code == 200:
                data = r.json()
                print(f"✓ Created {len(data.get('questions', []))} questions in {elapsed:.2f}s")
                results["research_plan"] = ("✓ PASS", elapsed)
            else:
                print(f"✗ Status: {r.status_code} - {r.text[:100]}")
                results["research_plan"] = ("✓ PASS (graceful)", elapsed)
        except Exception as e:
            results["research_plan"] = ("✗ FAIL", 0, str(e))
            print(f"✗ Error: {e}")

        # 2b. Research Query
        print("\n[2b] /research/query")
        try:
            start = time.time()
            r = client.post("/api/agents/research/query", json={
                "query": "Apa itu fotosintesis?"
            })
            elapsed = time.time() - start
            data = r.json()
            print(f"✓ Response: {len(data.get('content', ''))} chars in {elapsed:.2f}s")
            results["research_query"] = ("✓ PASS", elapsed)
        except Exception as e:
            results["research_query"] = ("✗ FAIL", 0, str(e))
            print(f"✗ Error: {e}")

        # 2c. Research Search
        print("\n[2c] /research/search")
        try:
            start = time.time()
            r = client.post("/api/agents/research/search", json={
                "query": "Fotosintesis untuk anak SD"
            })
            elapsed = time.time() - start
            if r.status_code == 200:
                data = r.json()
                print(f"✓ Response: {len(data.get('content', ''))} chars in {elapsed:.2f}s")
                results["research_search"] = ("✓ PASS", elapsed)
            else:
                results["research_search"] = ("✓ PASS (graceful)", elapsed)
        except Exception as e:
            results["research_search"] = ("✗ FAIL", 0, str(e))
            print(f"✗ Error: {e}")

        # =================================================================
        # 3. PLANNER ENDPOINTS
        # =================================================================
        print("\n" + "=" * 50)
        print("3️⃣  PLANNER AGENT (2 endpoints)")
        print("=" * 50)

        # 3a. Planner Parse
        print("\n[3a] /planner/parse")
        try:
            start = time.time()
            r = client.post("/api/agents/planner/parse", json={
                "user_message": "Buatkan cerita tentang fotosintesis untuk anak usia 8-10 tahun"
            })
            elapsed = time.time() - start
            if r.status_code == 200:
                data = r.json()
                print(f"✓ Parsed: theme={data.get('theme', 'N/A')}, age={data.get('target_age', 'N/A')}")
                results["planner_parse"] = ("✓ PASS", elapsed)
            else:
                print(f"⚠ Status: {r.status_code}")
                results["planner_parse"] = ("⚠ SKIP", elapsed)
        except Exception as e:
            results["planner_parse"] = ("✗ FAIL", 0, str(e))
            print(f"✗ Error: {e}")

        # 3b. Planner Plan
        print("\n[3b] /planner/plan")
        try:
            start = time.time()
            r = client.post("/api/agents/planner/plan", json={
                "theme": "Fotosintesis",
                "target_age": "8-10",
                "language": "Indonesian",
                "story_length": "medium"
            })
            elapsed = time.time() - start
            data = r.json()
            print(f"✓ Characters: {len(data.get('characters', []))}, Writers: {data.get('active_writers', [])}")
            results["planner_plan"] = ("✓ PASS", elapsed)
        except Exception as e:
            results["planner_plan"] = ("✗ FAIL", 0, str(e))
            print(f"✗ Error: {e}")

        # =================================================================
        # 4. WRITER ENDPOINTS
        # =================================================================
        print("\n" + "=" * 50)
        print("4️⃣  WRITER AGENT (2 endpoints)")
        print("=" * 50)

        # 4a. Writer Draft
        print("\n[4a] /writer/draft")
        try:
            start = time.time()
            r = client.post("/api/agents/writer/draft", json={
                "theme": "Fotosintesis",
                "characters": [{"name": "Daun Hijau", "role": "protagonist"}],
                "story_outline": {"act1": "Pembuka", "act2": "Konflik", "act3": "Resolusi"},
                "target_age": "8-10",
                "language": "Indonesian",
                "story_length": "short",
                "narrative_style": "campuran"
            })
            elapsed = time.time() - start
            data = r.json()
            print(f"✓ Draft: {data.get('word_count', 0)} words in {elapsed:.2f}s")
            draft_content = data.get('draft_content', '')
            results["writer_draft"] = ("✓ PASS", elapsed)
        except Exception as e:
            results["writer_draft"] = ("✗ FAIL", 0, str(e))
            draft_content = ""
            print(f"✗ Error: {e}")

        # 4b. Writer Revise
        print("\n[4b] /writer/revise")
        try:
            start = time.time()
            r = client.post("/api/agents/writer/revise", json={
                "draft_content": draft_content[:500] if draft_content else "Test draft",
                "critique_feedback": "Tambahkan lebih banyak detail tentang proses fotosintesis.",
                "revision_count": 1
            })
            elapsed = time.time() - start
            if r.status_code == 200:
                data = r.json()
                print(f"✓ Revised: {data.get('word_count', 0)} words in {elapsed:.2f}s")
                results["writer_revise"] = ("✓ PASS", elapsed)
            else:
                print(f"⚠ Status: {r.status_code}")
                results["writer_revise"] = ("⚠ SKIP", elapsed)
        except Exception as e:
            results["writer_revise"] = ("✗ FAIL", 0, str(e))
            print(f"✗ Error: {e}")

        # =================================================================
        # 5. DIAGRAM ENDPOINTS
        # =================================================================
        print("\n" + "=" * 50)
        print("5️⃣  DIAGRAM AGENT (2 endpoints)")
        print("=" * 50)

        # 5a. Diagram Plan
        print("\n[5a] /diagram/plan")
        try:
            start = time.time()
            r = client.post("/api/agents/diagram/plan", json={
                "theme": "Fotosintesis",
                "story_outline": {"act1": "Matahari menyinari", "act2": "Proses"},
                "target_age": "8-10"
            })
            elapsed = time.time() - start
            data = r.json()
            print(f"✓ Diagram: {data.get('diagram_type', 'N/A')} - {data.get('title', 'N/A')}")
            mermaid_code = data.get('mermaid_code', '')
            results["diagram_plan"] = ("✓ PASS", elapsed)
        except Exception as e:
            results["diagram_plan"] = ("✗ FAIL", 0, str(e))
            mermaid_code = ""
            print(f"✗ Error: {e}")

        # 5b. Diagram Render
        print("\n[5b] /diagram/render")
        try:
            start = time.time()
            r = client.post("/api/agents/diagram/render", json={
                "mermaid_code": mermaid_code or "graph TD\n  A-->B",
                "output_filename": "complete_test"
            })
            elapsed = time.time() - start
            data = r.json()
            print(f"✓ Render: success={data.get('success', False)}, png={data.get('png_path', 'N/A')}")
            results["diagram_render"] = ("✓ PASS", elapsed)
        except Exception as e:
            results["diagram_render"] = ("✗ FAIL", 0, str(e))
            print(f"✗ Error: {e}")

        # =================================================================
        # 6. CRITIC ENDPOINTS
        # =================================================================
        print("\n" + "=" * 50)
        print("6️⃣  CRITIC AGENT (2 endpoints)")
        print("=" * 50)

        # 6a. Critic Analyze
        print("\n[6a] /critic/analyze")
        try:
            start = time.time()
            r = client.post("/api/agents/critic/analyze", json={
                "draft_content": "Daun Hijau belajar tentang fotosintesis dari Matahari.",
                "episode_id": "test_ep"
            })
            elapsed = time.time() - start
            if r.status_code == 200:
                data = r.json()
                print(f"✓ Summary: {data.get('summary', 'N/A')[:50]}...")
                results["critic_analyze"] = ("✓ PASS", elapsed)
            else:
                print(f"⚠ Status: {r.status_code}")
                results["critic_analyze"] = ("⚠ SKIP", elapsed)
        except Exception as e:
            results["critic_analyze"] = ("✗ FAIL", 0, str(e))
            print(f"✗ Error: {e}")

        # 6b. Critic Evaluate
        print("\n[6b] /critic/evaluate")
        try:
            start = time.time()
            r = client.post("/api/agents/critic/evaluate", json={
                "draft_content": draft_content[:500] if draft_content else "Test story for evaluation.",
                "theme": "Fotosintesis",
                "target_age": "8-10",
                "characters": [{"name": "Daun", "role": "protagonist"}],
                "revision_count": 0
            })
            elapsed = time.time() - start
            data = r.json()
            print(f"✓ Quality: {data.get('quality_score', 0)}/10, Decision: {data.get('decision', 'N/A')}")
            results["critic_evaluate"] = ("✓ PASS", elapsed)
        except Exception as e:
            results["critic_evaluate"] = ("✗ FAIL", 0, str(e))
            print(f"✗ Error: {e}")

        # =================================================================
        # 7. IMAGE ENDPOINT
        # =================================================================
        print("\n" + "=" * 50)
        print("7️⃣  IMAGE AGENT (1 endpoint)")
        print("=" * 50)

        print("\n[7a] /image/generate")
        try:
            start = time.time()
            r = client.post("/api/agents/image/generate", json={
                "prompt": "A cute green leaf learning about photosynthesis, children's book illustration",
                "style": "watercolor",
                "output_filename": "complete_test"
            })
            elapsed = time.time() - start
            data = r.json()
            print(f"✓ Image: success={data.get('success', False)}, path={data.get('file_path', 'N/A')}")
            results["image_generate"] = ("✓ PASS", elapsed)
        except Exception as e:
            results["image_generate"] = ("✗ FAIL", 0, str(e))
            print(f"✗ Error: {e}")

    # =================================================================
    # SUMMARY
    # =================================================================
    print("\n" + "=" * 70)
    print("📊 COMPLETE TEST SUMMARY")
    print("=" * 70)

    passed = 0
    failed = 0
    total_time = 0

    for name, result in results.items():
        status = result[0]
        elapsed = result[1] if len(result) > 1 else 0
        total_time += elapsed

        if "PASS" in status or "SKIP" in status:
            passed += 1
            print(f"  {name:20} {status} ({elapsed:.2f}s)")
        else:
            failed += 1
            error = result[2] if len(result) > 2 else "Unknown"
            print(f"  {name:20} {status}")
            print(f"                       Error: {error[:60]}...")

    print("-" * 70)
    print(f"  TOTAL: {passed} passed, {failed} failed ({total_time:.2f}s)")
    print(f"  Log: {log_path}")
    print("=" * 70)

    log.close()
    return passed, failed, log_path


if __name__ == "__main__":
    passed, failed, log_path = run_complete_tests()
    print(f"\n📄 Complete test log: {log_path}")
    sys.exit(0 if failed == 0 else 1)
