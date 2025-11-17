import requests
from bs4 import BeautifulSoup

baseUrl = "https://1x-probet.com/en"
esportsUrl = "https://1x-probet.com/en/live/esports"


def get_title_from_url(url):
    print("Getting data from : {url}\n".format(url=url))
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    # Find the specific div group
    target_div = soup.find("div", class_="betting-main-dashboard")
    if not target_div:
        print("No div with class='betting-main-dashboard' found")
    else:
        # Find all li elements inside the div
        li_elements = target_div.find_all("li")

        results = []
        for li in li_elements:
            span = li.find("span", class_="ui-caption")
            if span:
                results.append(span.get_text(strip=True))

        print("Extracted values:")
        for idx, r in enumerate(results):
            print("{idx}: {r}".format(idx=idx, r=r))


get_title_from_url(baseUrl)
get_title_from_url(esportsUrl)
