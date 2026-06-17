"""Check stress-test engine status for a specific user.

Usage:
    python3 scripts/check_stress_test_status.py <username> <password>
"""
import sys
import requests

BASE = "http://localhost:8000"

def get_token(username: str, password: str) -> str:
    r = requests.post(f"{BASE}/auth/login", json={"username": username, "password": password}, timeout=5)
    r.raise_for_status()
    return r.json()["token"]

def check_status(username: str, password: str):
    try:
        token = get_token(username, password)
    except Exception as e:
        print(f"⚠️ LOGIN FAILED: {e}")
        sys.exit(1)

    url = f"{BASE}/api/v1/dashboard/stress-test-jobs"
    try:
        response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=5)
        response.raise_for_status()
        data = response.json()

        active = data.get("active_count", 0)
        total = data.get("total_count", 0)
        jobs = data.get("jobs", [])

        if active > 0:
            print(f"✅ STRESS TEST IS RUNNING: {active} active job(s) of {total} total")
            for j in jobs:
                if j["status"] == "running":
                    print(f"   • {j['job_id']}  {j['progress_pct']}%  stage={j['stage']}")
        else:
            print(f"❌ NO STRESS TESTS RUNNING: engine idle (total historical jobs: {total})")
            for j in jobs[-3:]:
                print(f"   • {j['job_id']}  status={j['status']}  stage={j['stage']}")

    except requests.exceptions.ConnectionError:
        print("⚠️ ERROR: Could not connect to the backend server. Is Uvicorn running on port 8000?")
        sys.exit(1)
    except Exception as e:
        print(f"⚠️ ERROR: An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: python3 {sys.argv[0]} <username> <password>")
        sys.exit(1)
    check_status(sys.argv[1], sys.argv[2])
