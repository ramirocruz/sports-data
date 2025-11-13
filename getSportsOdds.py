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

def fetch_odds(event, api_key, bookmakers):
    """Fetch odds for a single event."""
    event_id = event.get("id")
    try:
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


def fetch_all_odds(events, api_key, bookmakers, odds_limit, max_workers=15):
    """Fetch odds for multiple events concurrently."""
    odds_results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_event = {executor.submit(fetch_odds, event, api_key, bookmakers): event for event in events}
        for future in as_completed(future_to_event):
            result = future.result()
            if result:
                odds_results.append(result)
            if len(odds_results) >= odds_limit:
                return odds_results
    return odds_results


events = fetch_events('football', api_key)
odds = fetch_all_odds(events, api_key, bookmakers, 100)
print(odds)
