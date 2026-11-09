"""Heavy load for OpsBrain: asks for many different answers so the cache cannot help.
Usage:  $env:OPSBRAIN_URL="http://..."; python load_hard.py
Stop with Ctrl+C."""
import itertools, json, os, threading, time, urllib.request, urllib.error

URL = os.environ.get("OPSBRAIN_URL", "http://localhost:8000").rstrip("/")
THREADS = 12
SCEN = ["default", "degradation", "closure", "combined", "delay", "double"]
MODES = ["balanced", "oversized"]
ENGINES = ["rules", "optimiser"]
combos = [(s, m, e, n) for n in range(1, 11) for s in SCEN for m in MODES for e in ENGINES]
# optimiser answers cost the most CPU, so put them first
combos.sort(key=lambda c: c[2] != "optimiser")

done = {"ok": 0, "bad": 0}
lock = threading.Lock()

def worker(k):
    for i in itertools.count(k * 7):
        s, m, e, n = combos[i % len(combos)]
        body = json.dumps({"scenario": s, "mode": m, "engine": e, "top_n": n}).encode()
        req = urllib.request.Request(URL + "/analyse", body, {"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=120).read()
            key = "ok"
        except Exception:
            key = "bad"
            time.sleep(1)
        with lock:
            done[key] += 1

for k in range(THREADS):
    threading.Thread(target=worker, args=(k,), daemon=True).start()

print(f"Heavy load to {URL} with {THREADS} threads. Ctrl+C to stop.")
try:
    while True:
        time.sleep(10)
        print(f"ok: {done['ok']}   errors: {done['bad']}")
except KeyboardInterrupt:
    print("stopped")
