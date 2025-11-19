import requests
from requests.exceptions import ChunkedEncodingError
import json
from datetime import datetime
from collections import defaultdict
import os
from tabulate import tabulate
from rich.console import Console
from rich.table import Table
import pandas as pd


class OddsDisplayManager:
    """Manage and display odds in various tabular formats"""

    def __init__(self, odds_format='american', status='active'):
        self.odds_store = {}  # Store latest odds by fixture_id + market
        self.stats = {
            'total_updates': 0,
            'active_fixtures': set(),
            'locked_count': 0
        }
        self.odds_format = odds_format  # 'american', 'decimal', or 'fractional'
        self.status = status

    @staticmethod
    def american_to_decimal(american_odds):
        """Convert American odds to Decimal odds"""
        if american_odds is None:
            return None

        if american_odds > 0:
            # Positive odds: (American odds / 100) + 1
            return round((american_odds / 100) + 1, 2)
        else:
            # Negative odds: (100 / |American odds|) + 1
            return round((100 / abs(american_odds)) + 1, 2)

    @staticmethod
    def american_to_fractional(american_odds):
        """Convert American odds to Fractional odds"""
        if american_odds is None:
            return None

        if american_odds > 0:
            return f"{american_odds}/100"
        else:
            return f"100/{abs(american_odds)}"

    def format_price(self, price):
        """Format price based on selected format"""
        if price is None:
            return "N/A"

        if self.odds_format == 'decimal':
            return str(self.american_to_decimal(price))
        elif self.odds_format == 'fractional':
            return self.american_to_fractional(price)
        else:  # american (default)
            return f"{'+' if price > 0 else ''}{price}"

    def update_odds(self, odds_list, status='active'):
        """Update internal odds storage"""
        for odd in odds_list:
            key = odd.get('id', '##')

            self.odds_store[key] = {
                'fixture_id': odd['fixture_id'],
                'league': odd['league'],
                'market': odd['market'],
                'sportsbook': odd['sportsbook'],
                'name': odd['name'],
                'selection': odd.get('selection', ''),
                'price_american': odd['price'],  # Store original
                'price': self.format_price(odd['price']),  # Store formatted
                'points': odd.get('points'),
                'is_main': odd.get('is_main', False),
                'is_live': odd.get('is_live', False),
                'status': status,
                'last_updated': datetime.now().strftime('%H:%M:%S'),
                'game_id': odd['game_id']
            }

            self.stats['total_updates'] += 1
            self.stats['active_fixtures'].add(odd['fixture_id'])
            if status == 'locked':
                self.stats['locked_count'] += 1

    # ===== METHOD 1: Simple Text Table =====
    def display_simple_table(self, max_rows=20):
        """Display odds in a simple text table

        Args:
            max_rows: Maximum number of rows to display
        """
        os.system('clear' if os.name == 'posix' else 'cls')

        print("=" * 120)
        print(f"ODDS MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(
            f"Total Updates: {self.stats['total_updates']} | Active Fixtures: {len(self.stats['active_fixtures'])} | Locked: {self.stats['locked_count']}")
        print("=" * 120)

        if not self.odds_store:
            print("No odds data yet...")
            return

        # Original display logic
        odds_data = self.odds_store.values()
        if self.status != 'all':
            odds_data = filter(lambda x: x['status'] == self.status, odds_data)
        sorted_odds = sorted(odds_data,
                             key=lambda x: (x['fixture_id'], x['market'], -x['price_american']))

        print(
            f"\n{'League':<10} {'Market':<25} {'Book':<12} {'Selection':<30} {'Price':<8} {'Status':<8} {'Updated':<10}")
        print("-" * 120)

        for i, odd in enumerate(sorted_odds[:max_rows]):
            status_symbol = "🟢" if odd['status'] == 'active' else "🔴"
            print(f"{odd['league']:<10} {odd['market'][:24]:<25} {odd['sportsbook']:<12} "
                  f"{odd['name'][:29]:<30} {odd['price']:<8} {status_symbol} {odd['status']:<8} {odd['last_updated']:<10}")

    # ===== METHOD 2: Tabulate Library =====
    def display_tabulate(self, max_rows=20):
        """Display using tabulate library (prettier)

        Args:
            max_rows: Maximum number of rows to display
        """
        os.system('clear' if os.name == 'posix' else 'cls')

        print(f"\nODDS MONITOR - {datetime.now().strftime('%H:%M:%S')}")
        print(
            f"Updates: {self.stats['total_updates']} | Fixtures: {len(self.stats['active_fixtures'])} | Locked: {self.stats['locked_count']}\n")

        if not self.odds_store:
            print("No odds data yet...")
            return

        odds_data = self.odds_store.values()
        if self.status != 'all':
            odds_data = filter(lambda x: x['status'] == self.status, odds_data)
        sorted_odds = sorted(odds_data,
                             key=lambda x: (x['fixture_id'], x['market'], -x['price_american']))[:max_rows]

        table_data = []
        for odd in sorted_odds:
            table_data.append([
                odd['league'],
                odd['market'][:25],
                odd['sportsbook'],
                odd['name'][:30],
                odd['price'],
                "✓" if odd['status'] == 'active' else "✗",
                odd['last_updated']
            ])

        headers = ['League', 'Market', 'Sportsbook', 'Selection', 'Price', 'Status', 'Updated']
        print(tabulate(table_data, headers=headers, tablefmt='grid'))

    # ===== METHOD 3: Rich Library (Fancy) =====
    def display_rich(self):
        """Display using rich library with colors"""
        table = Table(title=f"📊 Live Odds Monitor - {datetime.now().strftime('%H:%M:%S')}")

        table.add_column("League", style="cyan", no_wrap=True)
        table.add_column("Market", style="magenta")
        table.add_column("Sportsbook", style="green")
        table.add_column("Selection", style="yellow")
        table.add_column("Price", justify="right", style="bold blue")
        table.add_column("Status", justify="center")
        table.add_column("Updated", style="dim")

        odds_data = self.odds_store.values()
        if self.status != 'all':
            odds_data = filter(lambda x: x['status'] == self.status, odds_data)
        sorted_odds = sorted(odds_data,
                             key=lambda x: (x['fixture_id'], x['market'], -x['price_american']))[:30]

        for odd in sorted_odds:
            status = "[green]✓ Active[/green]" if odd['status'] == 'active' else "[red]✗ Locked[/red]"
            table.add_row(
                odd['league'],
                odd['market'][:25],
                odd['sportsbook'],
                odd['name'][:30],
                str(odd['price']),
                status,
                odd['last_updated']
            )

        return table

    # ===== METHOD 4: Pandas DataFrame =====
    def get_dataframe(self):
        """Return odds as pandas DataFrame"""
        if not self.odds_store:
            return pd.DataFrame()

        odds_data = self.odds_store.values()
        if self.status != 'all':
            odds_data = filter(lambda x: x['status'] == self.status, odds_data)

        df = pd.DataFrame(list(odds_data))
        return df

    # ===== METHOD 5: Market Comparison View =====
    def display_market_comparison(self, fixture_id=None, market_filter=None):
        """Compare odds across sportsbooks for same market"""
        os.system('clear' if os.name == 'posix' else 'cls')

        print("=" * 100)
        print("SPORTSBOOK COMPARISON VIEW")
        print("=" * 100)

        # Group by fixture and market
        grouped = defaultdict(lambda: defaultdict(list))

        odds_data = self.odds_store.values()
        if self.status != 'all':
            odds_data = filter(lambda x: x['status'] == self.status, odds_data)

        for odd in odds_data:
            if fixture_id and odd['fixture_id'] != fixture_id:
                continue
            if market_filter and market_filter.lower() not in odd['market'].lower():
                continue

            key = f"{odd['fixture_id']}_{odd['market']}"
            grouped[key][odd['name']].append({
                'sportsbook': odd['sportsbook'],
                'price': odd['price'],
                'price_american': odd['price_american'],
                'status': odd['status']
            })

        for market_key, selections in grouped.items():
            print(f"\n{market_key}")
            print("-" * 100)

            for selection, books in selections.items():
                best_price = max(books, key=lambda x: x['price_american'] if x['status'] == 'active' else -9999)
                print(f"\n  {selection}:")

                for book in sorted(books, key=lambda x: -x['price_american']):
                    status = "✓" if book['status'] == 'active' else "✗"
                    best_marker = " ⭐ BEST" if book == best_price and book['status'] == 'active' else ""
                    print(f"    {book['sportsbook']:<15} {book['price']:>8} {status}{best_marker}")

    # ===== METHOD 6: CSV Export =====
    def export_to_csv(self, filename='odds_snapshot.csv'):
        """Export current odds to CSV"""
        df = self.get_dataframe()
        df.to_csv(filename, index=False)

        print(f"\n✓ Exported {len(self.odds_store)} odds to {filename}")


def stream_with_display(api_key, sport='football', display_method='simple', odds_format='decimal', status='active'):
    """Stream odds with chosen display method and odds format

    Args:
        api_key: Your OpticOdds API key
        sport: Sport to stream (football, esports, basketball, etc.)
        display_method: 'simple', 'tabulate', 'rich', 'comparison', 'dataframe'
        odds_format: 'american', 'decimal', or 'fractional'
        status: 'active', 'locked', or 'all'
    """

    # Fetch leagues
    response = requests.get(
        'https://api.opticodds.com/api/v3/leagues',
        params={'key': api_key, 'sport': sport}
    )
    leagues = [event.get('id') for event in response.json().get('data')]

    manager = OddsDisplayManager(odds_format=odds_format, status=status)
    last_entry_id = None
    update_counter = 0

    # For rich live display
    console = Console()

    while True:
        try:
            params = {
                "key": api_key,
                "sportsbook": ['1xbet'],
                "league": leagues,
            }
            if last_entry_id:
                params["last_entry_id"] = last_entry_id

            r = requests.get(
                f"https://api.opticodds.com/api/v3/stream/odds/{sport}",
                params=params,
                stream=True,
            )

            if r.status_code != 200:
                print(f"Error: {r.status_code} - {r.text}")
                break

            event_type = None
            event_data = []

            for line in r.iter_lines(decode_unicode=True):
                if not line or line == '':
                    if event_type and event_data:
                        data_str = '\n'.join(event_data)

                        try:
                            if event_type in ["odds", "locked-odds"]:
                                data = json.loads(data_str)
                                last_entry_id = data.get("entry_id")
                                odds_list = data.get("data", [])

                                status = 'active' if event_type == 'odds' else 'locked'
                                manager.update_odds(odds_list, status)

                                # Update display every 5 updates
                                if update_counter % 5 == 0:
                                    if display_method == 'simple':
                                        manager.display_simple_table()
                                    elif display_method == 'tabulate':
                                        manager.display_tabulate()
                                    elif display_method == 'rich':
                                        console.clear()
                                        console.print(manager.display_rich())
                                    elif display_method == 'comparison':
                                        manager.display_market_comparison()
                                    elif display_method == 'dataframe':
                                        df = manager.get_dataframe()
                                        print("\n" + "=" * 100)
                                        print(df.head(20).to_string())

                                update_counter += 1

                        except json.JSONDecodeError as je:
                            print(f"JSON error: {je}")

                        event_type = None
                        event_data = []
                    continue

                if line.startswith('event:'):
                    event_type = line.split(':', 1)[1].strip()
                elif line.startswith('data:'):
                    event_data.append(line.split(':', 1)[1].strip())
                elif line.startswith('retry:') or line.startswith('id:'):
                    pass
                else:
                    if event_data:
                        event_data.append(line)

        except ChunkedEncodingError:
            print("Reconnecting...")
        except KeyboardInterrupt:
            print("\nStopping...")
            # Export final snapshot
            manager.export_to_csv(f'odds_snapshot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
            break
        except Exception as e:
            print(f"Error: {e}")
            break


# ===== MAIN USAGE =====
if __name__ == "__main__":
    api_key = "c7d9514b-275f-4d64-9710-87f90922eed4"

    # Choose display method:
    # 'simple' - basic text table
    # 'tabulate' - prettier tables (requires: pip install tabulate)
    # 'rich' - fancy colored tables (requires: pip install rich)
    # 'comparison' - sportsbook comparison view
    # 'dataframe' - pandas dataframe (requires: pip install pandas)

    # Choose odds format:
    # 'american' - American odds (e.g., -110, +200)
    # 'decimal' - Decimal odds (e.g., 1.91, 3.00)
    # 'fractional' - Fractional odds (e.g., 10/11, 2/1)

    # Choose status of odds:
    # 'active' - Show only active odds
    # 'locked' - Show only locked odds
    # 'all' - Show all odds

    stream_with_display(
        api_key,
        sport='football',
        display_method='dataframe',
        odds_format='decimal',  # Change this to 'american' or 'fractional'
        status='active'
    )
