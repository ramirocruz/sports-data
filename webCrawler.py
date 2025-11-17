from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException

baseUrl = "https://1x-probet.com/en"
esportsUrl = "https://1x-probet.com/en/live/esports"

# Change to True to run headless
HEADLESS = False


def create_driver(headless=HEADLESS):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=options)
    return driver


def safe_find_element(parent, by, selector, default=None, wait=None, timeout=5):
    """
    Helper to find element safely either via parent element or driver.
    If wait is provided (WebDriverWait), will use presence_of_element_located on the selector relative to driver.
    """
    try:
        if wait is not None:
            # wait expects a (By, selector) tuple for the driver context
            return wait.until(EC.presence_of_element_located((by, selector)))
        else:
            return parent.find_element(by, selector)
    except (NoSuchElementException, TimeoutException, StaleElementReferenceException):
        return default


def safe_find_elements(parent, by, selector):
    try:
        return parent.find_elements(by, selector)
    except Exception:
        return []


def scrape_page(url):
    print(f"\nGetting data from: {url}\n")
    driver = create_driver()
    wait = WebDriverWait(driver, 20)
    driver.get(url)

    # initial wait for the main container (if present)
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.betting-main-dashboard")))
    except TimeoutException:
        # Not fatal — continue, maybe different page structure
        print("Warning: betting-main-dashboard not found quickly; continuing...")

    # Scroll a bit so JS may start rendering lazy content
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 4);")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

    results = []

    # Try to locate the main container (fallback to whole page)
    try:
        main_container = driver.find_element(By.CSS_SELECTOR, "div.betting-main-dashboard")
        li_items = main_container.find_elements(By.CSS_SELECTOR, "li.dashboard-champ-body")
    except NoSuchElementException:
        # fallback: collect all lis on page
        li_items = driver.find_elements(By.TAG_NAME, "li")

    print(f"Total LI items found: {len(li_items)}")

    for idx, li in enumerate(li_items):
        game_info = {}
        try:
            # Scroll this LI into view (virtualized lists require this)
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", li)
            time.sleep(0.25)  # give JS time to render this row

            # 1) heading: div.dashboard-champ-name span.ui-caption
            try:
                heading_elem = li.find_element(By.CSS_SELECTOR, "div.dashboard-champ-name span.ui-caption")
                game_info["heading"] = heading_elem.text.strip()
            except NoSuchElementException:
                continue

            # 2) game block: teams and scores
            try:
                game_block = li.find_element(By.CSS_SELECTOR, "div.dashboard-game-block")
                team_name_spans = safe_find_elements(game_block, By.CSS_SELECTOR, "span.dashboard-game-team-info__name")
                score_spans = safe_find_elements(game_block, By.CSS_SELECTOR, "span.ui-game-scores__num")

                # teams
                if len(team_name_spans) >= 2:
                    game_info["team1"] = team_name_spans[0].text.strip()
                    game_info["team2"] = team_name_spans[1].text.strip()
                elif len(team_name_spans) == 1:
                    game_info["team1"] = team_name_spans[0].text.strip()
                    game_info["team2"] = None
                else:
                    game_info["team1"] = None
                    game_info["team2"] = None

                # scores: spans come in pairs team1, team2, team1, team2...
                if score_spans:
                    scores = [s.text.strip() for s in score_spans]
                    team1_score = scores[::2]
                    team2_score = scores[1::2]
                    game_info["team1_score"] = team1_score
                    game_info["team2_score"] = team2_score
                else:
                    game_info["team1_score"] = []
                    game_info["team2_score"] = []
            except NoSuchElementException:
                # no game block
                game_info["team1"] = None
                game_info["team2"] = None
                game_info["team1_score"] = []
                game_info["team2_score"] = []

            # 3) odds inside div.dashboard-markets -> span.ui-market__value
            # First wait for dashboard-markets presence inside this li (some rows may not have it)
            odds = []
            try:
                # Use li.find_elements to search within this li subtree
                markets_divs = li.find_elements(By.CSS_SELECTOR, "div.dashboard-markets")
                if not markets_divs:
                    # optionally wait for ANY markets to appear globally (non-blocking)
                    # wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.dashboard-markets")))
                    pass

                for mdiv in markets_divs:
                    # collect ui-market__value spans inside this markets div
                    market_spans = safe_find_elements(mdiv, By.CSS_SELECTOR, "span.ui-market__value")
                    for s in market_spans:
                        text = s.text.strip()
                        if text:
                            odds.append(text)

                # Map odds to team1_win, draw, team2_win if at least 3 values
                if len(odds) >= 3:
                    # in your original code you assumed [0]=team1, [1]=draw, [2]=team2
                    game_info["team1_win"] = odds[0]
                    game_info["draw"] = odds[1]
                    game_info["team2_win"] = odds[2]
                else:
                    # still include odds list for inspection
                    game_info["odds_list"] = odds

            except Exception as e:
                # robust fallback
                game_info["odds_list"] = odds
                # optional: print(e)

            results.append(game_info)

        except StaleElementReferenceException:
            # If the LI becomes stale, skip or retry: here we append a placeholder
            results.append(
                {"heading": None, "team1": None, "team2": None, "team1_score": [], "team2_score": [], "odds_list": []})
        except Exception as e:
            # generic catch - avoid crashing whole loop
            print(f"Error processing li index {idx}: {e}")
            results.append({"error": str(e)})

    driver.quit()

    # Print extracted values
    print("Extracted values:")
    for i, r in enumerate(results):
        print(f"{i+1}: {r}")

    return results


if __name__ == "__main__":
    scrape_page(esportsUrl)
