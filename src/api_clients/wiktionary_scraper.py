import requests
from bs4 import BeautifulSoup

# Function to scrape word forms from Danish Wiktionary
def get_word_forms(word):
    url = f"https://da.wiktionary.org/wiki/{word}"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    forms = {}
    # Locate the conjugation or inflection table (HTML structure may vary)
    for table in soup.find_all("table", {"class": "inflection-table"}):
        for row in table.find_all("tr"):
            key = row.find("th").text.strip() if row.find("th") else None
            value = row.find("td").text.strip() if row.find("td") else None
            if key and value:
                forms[key] = value
    return forms

# Example usage:
# get_word_forms("spise") -> {'Present Tense': 'spiser', 'Past Tense': 'spiste', etc.}
