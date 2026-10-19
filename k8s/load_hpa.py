"""Sends many requests at once so the API uses CPU and Kubernetes adds pods.
Run:  python k8s/load_hpa.py        (Ctrl+C to stop)
Watch in another window:  kubectl get hpa,pods -n opsbrain -w"""
import itertools, json, os, threading, time, urllib.request

BASE = os.environ.get("OPSBRAIN_URL", "http://localhost:8080")
SCENARIOS = ["combined", "delay", "double", "default", "degradation", "closure"]
done = itertools.count(1)


def worker(offset):
    # a different top_n each time, so answers are not served from the cache
    for i in itertools.count(offset):
        body = {"scenario": SCENARIOS[i % 6], "engine": "optimiser",
                "mode": "balanced" if i % 2 else "oversized", "top_n": 1 + (i // 12) % 10}
        req = urllib.request.Request(BASE + "/analyse", json.dumps(body).encode(),
                                     {"content-type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=120).read()
        except Exception as e:
            print("error:", e)
            time.sleep(2)
        print("requests done:", next(done), end="\r")


for n in range(8):
    threading.Thread(target=worker, args=(n * 7,), daemon=True).start()
print("Sending load to", BASE, "- press Ctrl+C to stop")
while True:
    time.sleep(1)
