import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from ..config import BASE_URL
def get_html(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

def get_all_html_links():
    html = get_html(BASE_URL)
    soup = BeautifulSoup(html, "html.parser")
    return [urljoin(BASE_URL, link["href"]) for link in soup.find_all("a", href=True) if link["href"].endswith(".html")]

def extract_group_links():
    groups = {}
    for page_url in get_all_html_links():
        html = get_html(page_url)
        soup = BeautifulSoup(html, "html.parser")
        for header in soup.find_all("h1"):
            if "Grupa" in header.text:
                parts = header.text.strip().split()
                if len(parts) >= 2 and parts[1].isdigit():
                    groups[int(parts[1])] = page_url
    return groups
