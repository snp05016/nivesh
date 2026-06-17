import sys
import requests

def check_status():
    # Correct dashboard endpoint — not a job-specific URL
    url = "http://localhost:8000/api/v1/dashboard/stress-test-jobs"
    try:
        response = requests.get(url, timeout=5)
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
    check_status()
