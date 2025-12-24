import requests
from bs4 import BeautifulSoup

def nextdoor_search(query, location):
    url = f"https://nextdoor.com/business/search/?query={query}&near={location}"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    results = []
    for biz in soup.select("li.business-card"):
        name = biz.select_one(".business-card__name")
        desc = biz.select_one(".business-card__category")

        results.append({
            "name": name.get_text(strip=True) if name else "",
            "description": desc.get_text(strip=True) if desc else "",
            "source": "nextdoor"
        })

    return results