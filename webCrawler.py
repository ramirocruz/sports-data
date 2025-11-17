import requests
from bs4 import BeautifulSoup

url = "https://1x-probet.com/en"  # Replace with the website you are studying

response = requests.get(url)
response.raise_for_status()  # Fails if the request is bad

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
        span = li.find("span")
        if span:
            results.append(span.get_text(strip=True))

    print("Extracted values:")
    for r in results:
        print(r)
