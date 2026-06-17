import sys
import requests
import time

def check_status():
    url = "http://localhost:8000/api/v1/portfolio/stress-test/status"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        is_running = data.get("is_running", False)
        count = data.get("active_count", 0)
        
        if is_running:
            print(f"✅ STRESS TEST IS RUNNING: There are currently {count} active stress test(s) being processed.")
        else:
            print("❌ NO STRESS TESTS RUNNING: The stress test engine is currently idle.")
            
    except requests.exceptions.ConnectionError:
        print("⚠️ ERROR: Could not connect to the backend server. Is Uvicorn running on port 8000?")
        sys.exit(1)
    except Exception as e:
        print(f"⚠️ ERROR: An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_status()
