
import httpx
import json

def test_workflow_stream():
    print("\n🧪 Testing Workflow SSE Stream...")
    url = "http://localhost:8000/api/workflow/generate"
    payload = {"prompt": "Cerita pendek tentang robot yang belajar melukis"}
    
    print(f"POST {url}")
    print(f"Payload: {payload}")
    
    API_KEY = "H4kaGxsHHU93P6u_1T0IQN3aRxRYDGwXX1ABFZ5QPQk"
    headers = {"X-API-Key": API_KEY}
    
    try:
        with httpx.stream("POST", url, json=payload, headers=headers, timeout=300.0) as response:
            print(f"Status: {response.status_code}")
            if response.status_code != 200:
                print(response.read().decode())
                return

            print("Streaming events:")
            for line in response.iter_lines():
                if line.startswith("event: "):
                    event_type = line[7:]
                    print(f"\n[{event_type}]", end=" ")
                elif line.startswith("data: "):
                    data = json.loads(line[6:])
                    # Print summary of data to keep clean
                    keys = list(data.keys())
                    print(f"{keys}", end="")
                    
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    test_workflow_stream()
