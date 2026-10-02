import urllib.request
import json
import time

payload = {
    "name": "web-api-validation",
    "base_url": "http://127.0.0.1:11434/v1",
    "model": "qwen2.5:0.5b",
    "concurrency": [1, 2],
    "repetitions": 1,
    "requests_per_point": 2,
    "warmup_requests": 0,
    "prompts": ["What is a cache?"],
    "max_tokens": 16,
    "slo": {
        "max_ttft_p95_ms": 1000.0,
        "max_total_latency_p95_ms": 2500.0,
        "max_error_rate_pct": 1.0,
        "min_throughput_req_per_sec": 1.0,
    },
}

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/experiments",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req) as resp:
    res_data = json.loads(resp.read().decode())
    print("Experiment launched:", res_data)
    job_id = res_data["job_id"]

# Poll for completion
for i in range(30):
    time.sleep(1)
    with urllib.request.urlopen(f"http://127.0.0.1:8000/api/experiments/{job_id}") as poll_resp:
        status_data = json.loads(poll_resp.read().decode())
        curr = status_data.get("progress_current")
        tot = status_data.get("progress_total")
        trial = status_data.get("current_trial")
        st = status_data.get("status")
        print(f"Poll {i+1}: status={st}, progress={curr}/{tot}, trial={trial}")
        if st == "completed":
            print("\nEXPERIMENT COMPLETED SUCCESSFULLY!")
            cap = status_data.get("capacity", {})
            print("Highest Observed Compliant Tested Concurrency:", cap.get("highest_compliant_concurrency"))
            break
        elif st == "failed":
            print("EXPERIMENT FAILED:", status_data.get("error"))
            break
