"""Fetch all closed Polymarket markets from the Gamma API (with tags and embedded events).

python src/polymarket_fetch.py -> data/polymarket/api/markets.jsonl (raw market records, resumable)
"""
import http.client, json, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

API = "https://gamma-api.polymarket.com/"
OUT = Path(__file__).resolve().parents[1] / "data/polymarket/api"

def get(endpoint, **params):
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    for attempt in range(8):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise
        except (OSError, http.client.HTTPException):
            pass
        time.sleep(2**attempt)
    raise RuntimeError(f"giving up on {url}")

def fetch():
    OUT.mkdir(parents=True, exist_ok=True)
    state_path = OUT / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"cursor": None, "size": 0, "n": 0}
    with open(OUT / "markets.jsonl", "a+b") as f:
        f.truncate(state["size"])  # drop a page half-written before a kill
        while True:
            params = {"closed": "true", "include_tag": "true", "limit": 100}
            if state["cursor"]:
                params["after_cursor"] = state["cursor"]
            page = get("markets/keyset", **params)
            for m in page["markets"]:
                f.write((json.dumps(m) + "\n").encode())
            f.flush()
            state = {"cursor": page.get("next_cursor"), "size": f.tell(), "n": state["n"] + len(page["markets"])}
            state_path.write_text(json.dumps(state))
            if state["n"] % 10000 < 100:
                print(state["n"], flush=True)
            if not state["cursor"]:
                break
            time.sleep(0.1)

if __name__ == "__main__":
    fetch()
