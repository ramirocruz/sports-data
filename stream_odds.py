import requests
from requests.exceptions import ChunkedEncodingError
import json

last_entry_id: str | None = None
api_key = "c7d9514b-275f-4d64-9710-87f90922eed4"

while True:
    try:
        params = {
            "key": api_key,
            "sportsbook": ["DraftKings", "FanDuel", "Hard Rock", "Pinnacle", "1xbet"],
            "league": "NCAAF",
            "include_fixture_updates": True
        }
        if last_entry_id:
            params["last_entry_id"] = last_entry_id

        print("Connecting to stream...")
        r = requests.get(
            "https://api.opticodds.com/api/v3/stream/odds/football",
            params=params,
            stream=True,
        )

        print(f"Connection status: {r.status_code}")
        if r.status_code != 200:
            print(f"Error: {r.status_code} - {r.text}")
            break

        print("Connected! Waiting for events...")

        # Manual SSE parsing
        event_type = None
        event_id = None
        event_data = []

        for line in r.iter_lines(decode_unicode=True):
            # Empty line indicates end of event
            if not line or line == '':
                if event_type and event_data:
                    data_str = '\n'.join(event_data)

                    try:
                        if event_type in ["odds", "locked-odds", "fixture-status"]:
                            data = json.loads(data_str)

                            if event_type == "odds":
                                last_entry_id = data.get("entry_id")
                                print(f"\n=== ODDS EVENT ===")
                                print(json.dumps(data, indent=2))
                            elif event_type == "locked-odds":
                                last_entry_id = data.get("entry_id")
                                print(f"\n=== LOCKED ODDS EVENT ===")
                                print(json.dumps(data, indent=2))
                            elif event_type == "fixture-status":
                                print(f"\n=== FIXTURE STATUS EVENT ===")
                                print(json.dumps(data, indent=2))
                        else:
                            print(f"\n=== {event_type.upper()} EVENT ===")
                            print(data_str)
                    except json.JSONDecodeError as je:
                        print(f"JSON decode error for {event_type}: {je}")
                        print(f"Raw data: {data_str}")

                    # Reset for next event
                    event_type = None
                    event_id = None
                    event_data = []
                continue

            # Parse SSE fields
            if line.startswith('event:'):
                event_type = line.split(':', 1)[1].strip()
            elif line.startswith('id:'):
                event_id = line.split(':', 1)[1].strip()
            elif line.startswith('data:'):
                event_data.append(line.split(':', 1)[1].strip())
            elif line.startswith('retry:'):
                pass  # Ignore retry field
            else:
                # If line doesn't start with a field name, it's a continuation of data
                if event_data:
                    event_data.append(line)

    except ChunkedEncodingError as ex:
        print(f"\nDisconnected: {ex}, attempting to reconnect...")
    except KeyboardInterrupt:
        print("\nStopping...")
        break
    except Exception as e:
        print(f"\nError: {type(e).__name__} - {e}")
        import traceback

        traceback.print_exc()
        break
