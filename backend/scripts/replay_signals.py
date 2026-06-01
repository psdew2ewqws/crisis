"""Replay seed signals via POST /api/v1/signals at accelerated time."""
import json
import time
import argparse
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--speed", type=int, default=60, help="Time multiplier (60x = incident in ~45s)")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--seed", default="./data/seeds/zarqa.json")
    args = parser.parse_args()

    data = json.load(open(args.seed))
    signals = sorted(data["signals"], key=lambda s: s["t_offset_s"])

    print(f"Replaying {len(signals)} signals at {args.speed}x speed...")
    start = time.time()

    for i, sig in enumerate(signals):
        if sig.get("unrelated"):
            print(f"  [skip] {sig['id']} (unrelated)")
            continue

        # Wait proportional time
        if i > 0:
            prev_offset = signals[i - 1]["t_offset_s"]
            delay = (sig["t_offset_s"] - prev_offset) / args.speed
            if delay > 0:
                time.sleep(delay)

        payload = {
            "id": sig["id"],
            "observes": sig["observes"],
            "metric": sig["metric"],
            "value": sig["value"],
            "baseline": sig["baseline"],
            "t_offset_s": sig["t_offset_s"],
            "severity_raw": sig["severity_raw"],
        }
        resp = httpx.post(f"{args.base_url}/api/v1/signals", json=payload)
        elapsed = time.time() - start
        print(f"  [{elapsed:5.1f}s] POST {sig['id']} -> {resp.status_code}")

    print("Replay complete.")


if __name__ == "__main__":
    main()
