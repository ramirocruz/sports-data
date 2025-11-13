import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

import requests

date = datetime.today().date()

UTC = timezone.utc
end = datetime.combine(date, datetime.min.time(), UTC)
start = datetime.combine(date - timedelta(days=1), datetime.min.time(), UTC) - timedelta(seconds=1)

start = start.isoformat().replace("+00:00", "Z")
end = end.isoformat().replace("+00:00", "Z")
print("Start:", start)
print("End:  ", end)

api_key = ""
bookmakers = '1xbet'


def get_all_sports():
    url = "https://api.odds-api.io/v3/sports"
    response = requests.get(url)
    return response.json()


def fetch_events(sport, api_key):
    response = requests.get(
        'https://api.odds-api.io/v3/events',
        params={
            'apiKey': api_key,
            'sport': sport,
            'limit': 10,
        }
    )
    events = response.json()
    return events


def fetch_events_with_status(sport, api_key, status):
    response = requests.get(
        'https://api.odds-api.io/v3/events',
        params={
            'apiKey': api_key,
            'sport': sport,
            'status': status,
            'limit': 10,
        }
    )
    events = response.json()
    return events


def fetch_odds(event, api_key, bookmakers, stop_flag):
    """Fetch odds for a single event."""
    if stop_flag.is_set():
        return None

    try:
        event_id = event.get("id")
        response = requests.get(
            "https://api.odds-api.io/v3/odds",
            params={
                "apiKey": api_key,
                "eventId": event_id,
                "bookmakers": bookmakers
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        if len(data.get('bookmakers')):
            print(f"✅ Got odds for event {event_id}")
            return data

        print(f"⚠️ Got details for the event {event_id} without odds")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching odds for {event_id}: {e}")
        return None
    except Exception as e:
        print(f"❌ Error fetching odds: {e}")
        return None


def fetch_multi_odds(events, api_key, bookmakers, stop_flag):
    """Fetch odds for a multi event upto 10."""
    if stop_flag.is_set():
        return None

    try:
        event_ids = [event.get("id") for event in events if isinstance(event, dict)]
        response = requests.get(
            "https://api.odds-api.io/v3/odds/multi",
            params={
                "apiKey": api_key,
                "eventIds": event_ids,
                "bookmakers": bookmakers
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        data = [event for event in data if len(event.get("bookmakers"))]

        return data
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching odds for {event_ids}: {e}")
        return None
    except Exception as e:
        print(f"❌ Error fetching odds: {e}")
        return None


def chunk_events(events, chunk_size=10):
    """Split events into chunks of given size."""
    for i in range(0, len(events), chunk_size):
        yield events[i:i + chunk_size]


def fetch_all_odds(events, api_key, bookmakers, odds_limit=None, max_workers=15):
    odds_results = []
    stop_flag = threading.Event()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(fetch_multi_odds, event, api_key, bookmakers, stop_flag)
            for event in events
        ]

        for future in as_completed(futures):
            if stop_flag.is_set():
                break

            result = future.result()
            if result and len(result):
                odds_results.extend(result)

            if odds_limit and len(odds_results) >= odds_limit:
                stop_flag.set()  # signal all threads to stop further work
                break

    return odds_results


def get_odds_for_all_sport(api_key, bookmakers, status, odds_limit, events_limit=None):
    sports = get_all_sports()
    sports_odds = {}
    for sport in sports:
        print("Started for sport", sport)
        events = fetch_events_with_status(sport.get('slug'), api_key, status)
        events = events[:events_limit] if events_limit else events
        chunks = [events[i:i+10] for i in range(0, len(events), 10)]
        odds = fetch_all_odds(chunks, api_key, bookmakers, odds_limit)
        sports_odds[sport.get('slug')] = odds
        print("Finished for sport", sport)
    return sports_odds


if __name__ == "__main__":
    sports_odds = get_odds_for_all_sport(api_key, bookmakers, 'pending', odds_limit=5, events_limit=1000)
    print(sports_odds)
