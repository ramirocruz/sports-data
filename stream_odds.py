import requests
import json
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional
from requests.exceptions import ChunkedEncodingError, RequestException
from tabulate import tabulate


def fetch_leagues(sport, api_key):
    response = requests.get(
        'https://api.opticodds.com/api/v3/leagues',
        params={
            'key': api_key,
            'sport': sport
        }
    )
    events = response.json()
    return [event.get('id') for event in events.get('data')]

class OpticOddsManager:
    """Lightweight version — no DB, only prints odds in tabular form."""

    def __init__(self, api_key: str, auto_print_interval: int = 5):
        self.api_key = api_key
        self.last_entry_id: Optional[str] = None
        self.auto_print_interval = auto_print_interval
        self._stop_printer = False

        # in-memory odds: { odds_id → odds object }
        self.odds_store: Dict[str, Dict] = {}

    # ------------------------------------
    # Convert American → Decimal
    # ------------------------------------
    @staticmethod
    def american_to_decimal(american):
        if american is None:
            return None
        try:
            american = float(american)
        except:
            return None

        if american > 0:
            return (american / 100) + 1
        else:
            return (100 / abs(american)) + 1

    # ------------------------------------
    # Upsert odds into in-memory store
    # ------------------------------------
    def upsert_odds(self, data_list: List[Dict]):
        for odd in data_list:
            oid = odd.get("id")
            if not oid:
                continue

            # keep a raw (unmodified) copy
            odd["_raw"] = dict(odd)

            # decimal conversion only for display table
            odd["decimal_price"] = self.american_to_decimal(odd.get("price"))
            self.odds_store[oid] = odd

    # ------------------------------------
    # Safe JSON parsing for SSE
    # ------------------------------------
    @staticmethod
    def _parse_json_safe(s: str):
        s = s.strip()
        if not s:
            raise ValueError("Empty JSON string")

        try:
            return json.loads(s)
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
            idx = 0
            while idx < len(s):
                try:
                    obj, end = decoder.raw_decode(s[idx:])
                    return obj
                except json.JSONDecodeError:
                    idx += 1
            raise

    # ------------------------------------
    # Print the table (same structure)
    # ------------------------------------
    def print_live_table(self):
        rows = list(self.odds_store.values())
        if not rows:
            print("\nNo odds received yet...")
            return

        # Group by fixture → sportsbook
        fixtures = {}
        for r in rows:
            fid = r.get("fixture_id") or "unknown"
            fixtures.setdefault(fid, {"league": r.get("league"), "sport": r.get("sport"), "books": {}})
            fixtures[fid]["books"].setdefault(r["sportsbook"], []).append(r)

        table = []

        for fid, meta in fixtures.items():
            for sb, entries in meta["books"].items():

                # pick up to 2 selections
                seen = {}
                for e in entries:
                    key = e.get("selection") or e.get("name")
                    if key not in seen:
                        seen[key] = e
                    if len(seen) >= 2:
                        break

                selected = list(seen.values())

                if len(selected) == 0:
                    continue
                if len(selected) == 1:  # pad second column
                    selected.append({"name": "", "decimal_price": ""})

                t1, t2 = selected[0], selected[1]

                table.append([
                    fid,
                    meta["league"] or "",
                    sb,
                    t1.get("name") or t1.get("selection") or "",
                    t1.get("decimal_price") or "",
                    t2.get("name") or t2.get("selection") or "",
                    t2.get("decimal_price") or "",
                ])

        print("\n" + "=" * 72)
        print(f" LIVE ODDS — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 72)
        print(tabulate(
            table,
            headers=["Fixture ID", "League", "Sportsbook", "Team A", "Odds A", "Team B", "Odds B"],
            tablefmt="fancy_grid"
        ))
        print("=" * 72 + "\n")

    def print_raw_table(self):
        rows = list(self.odds_store.values())
        if not rows:
            print("\nNo odds received yet...")
            return

        # Extract the raw dicts
        raw_rows = [r["_raw"] for r in rows]

        # Determine ALL possible keys dynamically
        all_keys = sorted({k for row in raw_rows for k in row.keys()})

        # Build table
        table = []
        for row in raw_rows:
            table.append([row.get(k, "") for k in all_keys])

        print("\n" + "=" * 72)
        print(f" RAW ODDS (No Decimal Conversion) — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 72)
        print(tabulate(
            table,
            headers=all_keys,
            tablefmt="fancy_grid"
        ))
        print("=" * 72 + "\n")

    # ------------------------------------
    # Stream and process events
    # ------------------------------------
    def stream_odds(self, sport: str,
                    league_ids=None,
                    fixture_ids=None,
                    sportsbooks=None,
                    markets=None,
                    show_raw_table=True,
                    verbose=True):

        # Background printer
        def printer_thread():
            while not self._stop_printer:
                time.sleep(self.auto_print_interval)
                try:
                    self.print_live_table()
                    if show_raw_table:
                        self.print_raw_table()  # NEW TABLE
                except Exception as e:
                    print("[printer] error:", e)

        threading.Thread(target=printer_thread, daemon=True).start()

        url = f"https://api.opticodds.com/api/v3/stream/odds/{sport}"
        backoff = 1

        while True:
            try:
                params = {}
                if league_ids:
                    params["league"] = league_ids
                if fixture_ids:
                    params["fixture_id"] = fixture_ids
                if sportsbooks:
                    params["sportsbook"] = sportsbooks
                if markets:
                    params["market"] = markets
                if self.last_entry_id:
                    params["last_entry_id"] = self.last_entry_id

                params["include_fixture_updates"] = True

                headers = {
                    "Accept": "text/event-stream",
                    "Connection": "keep-alive",
                    "X-API-KEY": self.api_key
                }

                params_with_key = dict(params, key=self.api_key)

                print(f"\n[{datetime.now()}] Connecting to SSE stream...")
                r = requests.get(url, headers=headers, params=params_with_key, stream=True, timeout=90)
                print(f"[{datetime.now()}] Status = {r.status_code}")

                if r.status_code != 200:
                    print("Bad response: ", r.text[:300])
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                    continue

                backoff = 1
                print("Connected! Listening for odds…")

                event_type = None
                data_parts = []

                for raw in r.iter_lines(decode_unicode=True):
                    if raw is None:
                        continue

                    line = raw.strip()

                    # Debug raw line
                    if verbose:
                        print("RAW:", repr(line))

                    if line.startswith("event:"):
                        event_type = line.split(":", 1)[1].strip()
                        continue

                    if line.startswith("data:"):
                        data_parts.append(line.split(":", 1)[1].strip())
                        continue

                    if line == "" and (event_type or data_parts):
                        full_data = "\n".join(data_parts).strip()

                        if event_type in ("odds", "locked-odds"):
                            try:
                                payload = self._parse_json_safe(full_data)
                            except Exception as ex:
                                print("JSON parse error:", ex)
                                print(full_data)
                                event_type = None
                                data_parts = []
                                continue

                            if isinstance(payload, dict) and payload.get("entry_id"):
                                self.last_entry_id = payload["entry_id"]

                            data_list = payload.get("data") or []

                            if event_type == "odds":
                                self.upsert_odds(data_list)
                                print(f"[{datetime.now()}] ✓ Received {len(data_list)} odds")

                            elif event_type == "locked-odds":
                                print("[locked-odds] received")

                        event_type = None
                        data_parts = []
                        continue

                print("Stream ended. Reconnecting...")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)

            except Exception as e:
                print("Error:", e)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)

    # ------------------------------------
    def stop(self):
        self._stop_printer = True


# -----------------------------------------
# USAGE
# -----------------------------------------
if __name__ == "__main__":
    api_key = "c7d9514b-275f-4d64-9710-87f90922eed4"

    manager = OpticOddsManager(api_key=api_key, auto_print_interval=5)
    sport = 'football'

    print(f"Starting {sport} stream…")

    leagues = fetch_leagues(sport, api_key)
    print(f"Leagues are ... {leagues}")
    sportsbooks = ["1xbet"]

    manager.stream_odds(
        sport=sport,
        league_ids=leagues,
        sportsbooks=sportsbooks,
        show_raw_table=False,
        verbose=False
    )
