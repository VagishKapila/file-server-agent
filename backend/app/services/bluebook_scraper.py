import requests
from bs4 import BeautifulSoup

def bluebook_search(query, location):
    url = f"https://thebluebook.com/search.html?search_term={query}+contractor+{location}"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    results = []
    for card in soup.select(".company-result"):
        name = card.select_one(".company-name")
        address = card.select_one(".company-address")

        results.append({
            "name": name.get_text(strip=True) if name else "",
            "address": address.get_text(strip=True) if address else "",
            "source": "bluebook"
        })

    return results