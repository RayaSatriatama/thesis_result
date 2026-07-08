"""
Run All API Tests
Test runner for Story Agent API endpoints with logging
"""

import sys
import httpx
import time
from datetime import datetime
from pathlib import Path
import os
# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Test modules
from tests.api import test_health
from tests.api import test_research
from tests.api import test_planner
from tests.api import test_writer
from tests.api import test_diagram
from tests.api import test_critic
from tests.api import test_image
from tests.api import test_workflow


import argparse

# Parser setup
parser = argparse.ArgumentParser(description="Run Story Agent API Tests")
parser.add_argument("--enable-image", action="store_true", help="Enable image generation in workflow test")
parser.add_argument("--enable-diagram", action="store_true", help="Enable diagram generation in workflow test")
args = parser.parse_args()

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


def run_all_tests(args=None):
    """Run all API tests sequentially with logging"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = LOG_DIR / f"api_test_{timestamp}.log"
    
    # Set up logging
    log = LogCapture(log_path)
    sys.stdout = log
    
    print("=" * 70)
    print(f"🧪 STORY AGENT API TEST SUITE")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Server: {BASE_URL}")
    print(f"   Log: {log_path}")
    print("=" * 70)
    
    results = {}
    total_time = 0
    
    with httpx.Client(base_url=BASE_URL, timeout=300.0) as client:
        # 1. Health Check
        print("\n" + "=" * 50)
        print("1️⃣  HEALTH CHECK")
        print("=" * 50)
        try:
            start = time.time()
            test_health.test_health_check(client)
            test_health.test_openapi_docs(client)
            elapsed = time.time() - start
            results["health"] = ("✓ PASS", elapsed, None)
        except Exception as e:
            results["health"] = ("✗ FAIL", 0, str(e))
            print(f"Error: {e}")
        
        # 2. Research Agent
        print("\n" + "=" * 50)
        print("2️⃣  RESEARCH AGENT")
        print("=" * 50)
        try:
            start = time.time()
            test_research.test_research_query(client)
            elapsed = time.time() - start
            results["research"] = ("✓ PASS", elapsed, None)
        except Exception as e:
            results["research"] = ("✗ FAIL", 0, str(e))
            print(f"Error: {e}")
        
        # 3. Planner Agent
        print("\n" + "=" * 50)
        print("3️⃣  PLANNER AGENT")  
        print("=" * 50)
        try:
            start = time.time()
            test_planner.test_planner_plan(client, "Fotosintesis", "8-10")
            elapsed = time.time() - start
            results["planner"] = ("✓ PASS", elapsed, None)
        except Exception as e:
            results["planner"] = ("✗ FAIL", 0, str(e))
            print(f"Error: {e}")
        
        # 4. Writer Agent
        print("\n" + "=" * 50)
        print("4️⃣  WRITER AGENT")
        print("=" * 50)
        try:
            start = time.time()
            test_writer.test_writer_draft(client, "Fotosintesis", "8-10")
            elapsed = time.time() - start
            results["writer"] = ("✓ PASS", elapsed, None)
        except Exception as e:
            results["writer"] = ("✗ FAIL", 0, str(e))
            print(f"Error: {e}")
        
        # 5. Diagram Agent
        print("\n" + "=" * 50)
        print("5️⃣  DIAGRAM AGENT")
        print("=" * 50)
        try:
            start = time.time()
            test_diagram.test_diagram_plan(client, "Fotosintesis", "8-10")
            test_diagram.test_diagram_render(client)
            elapsed = time.time() - start
            results["diagram"] = ("✓ PASS", elapsed, None)
        except Exception as e:
            results["diagram"] = ("✗ FAIL", 0, str(e))
            print(f"Error: {e}")
        
        # 6. Critic Agent
        print("\n" + "=" * 50)
        print("6️⃣  CRITIC AGENT")
        print("=" * 50)
        try:
            start = time.time()
            test_critic.test_critic_evaluate(client, "Fotosintesis", "8-10")
            elapsed = time.time() - start
            results["critic"] = ("✓ PASS", elapsed, None)
        except Exception as e:
            results["critic"] = ("✗ FAIL", 0, str(e))
            print(f"Error: {e}")
        
        # 8. Workflow
        print("\n" + "=" * 50)
        print("8️⃣  FULL WORKFLOW")
        print("=" * 50)
        try:
            start = time.time()
            
            # Determine active writers based on args
            active_writers = ["text"]
            if args and args.enable_image:
                active_writers.append("image")
            if args and args.enable_diagram:
                active_writers.append("diagram")
                
            test_workflow.test_workflow_generate_stream(client, active_writers=active_writers)
            elapsed = time.time() - start
            results["workflow"] = ("✓ PASS", elapsed, None)
        except Exception as e:
            results["workflow"] = ("✗ FAIL", 0, str(e))
            print(f"Error: {e}")
    
        # 7. Image Agent
        print("\n" + "=" * 50)
        print("7️⃣  IMAGE AGENT")
        print("=" * 50)
        try:
            start = time.time()
            test_image.test_image_generate(client)
            elapsed = time.time() - start
            results["image"] = ("✓ PASS", elapsed, None)
        except Exception as e:
            results["image"] = ("✗ FAIL", 0, str(e))
            print(f"Error: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    passed = 0
    failed = 0
    for name, (status, elapsed, error) in results.items():
        total_time += elapsed
        if status.startswith("✓"):
            passed += 1
            print(f"  {name.upper():12} {status} ({elapsed:.2f}s)")
        else:
            failed += 1
            print(f"  {name.upper():12} {status}")
            if error:
                print(f"               Error: {error[:80]}...")
    
    print("-" * 70)
    print(f"  TOTAL: {passed} passed, {failed} failed ({total_time:.2f}s)")
    print(f"  Log file: {log_path}")
    print("=" * 70)
    
    # Close log
    log.close()
    
    return passed, failed, log_path


if __name__ == "__main__":
    passed, failed, log_path = run_all_tests(args)
    print(f"\n📄 Test log saved to: {log_path}")
    sys.exit(0 if failed == 0 else 1)
