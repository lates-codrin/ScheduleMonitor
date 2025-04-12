from bs4 import BeautifulSoup
import pandas as pd
import json
import requests
from ..config import BASE_URL

def parse_timetable_from_url(url, group_nr):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    header = next((h for h in soup.find_all('h1') if f"Grupa {group_nr}" in h.text), None)
    if not header:
        return None

    table = header.find_next('table')
    if not table:
        return []

    df = pd.DataFrame(columns=['Ziua', 'Orele', 'Sala', 'Frecventa', 'Formatia', 'Tipul', 'Disciplina', 'CD'])
    for row in table.find_all('tr'):
        cols = row.find_all('td')
        if len(cols) >= 8:
            df = df._append({
                'Ziua': cols[0].text.strip(),
                'Orele': cols[1].text.strip(),
                'Sala': cols[3].text.strip(),
                'Frecventa': cols[2].text.strip(),
                'Formatia': cols[4].text.strip(),
                'Tipul': cols[5].text.strip(),
                'Disciplina': cols[6].text.strip(),
                'CD': cols[7].text.strip()
            }, ignore_index=True)
    return json.loads(df.to_json(orient="records"))

def parse_news(news_html):
    soup = BeautifulSoup(news_html, 'html.parser')
    articles = []

    for post in soup.find_all("div", class_="post-box"):
        title_tag = post.find("h2", class_="title").find("a")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        link = title_tag.get("href")
        date_tag = post.find("span", class_="meta_date")
        date = date_tag.get_text(strip=True) if date_tag else "N/A"
        description_tag = post.find("div", class_="entry")
        description = description_tag.get_text(strip=True) if description_tag else ""
        img_tag = description_tag.find("img") if description_tag else None
        image_url = BASE_URL + img_tag['src'].lstrip('.') if img_tag else BASE_URL + "cslogo.png"

        articles.append({
            "articleTitle": title,
            "articleDescription": description,
            "articleDate": date,
            "articleLink": link,
            "articleImage": image_url
        })
    return articles

def parse_rooms(html):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', {'border': '1'})
    if not table:
        return []

    rows = table.find_all('tr')[1:]
    rooms = []

    for row in rows:
        cols = row.find_all('td')
        if len(cols) > 1:
            rooms.append({
                "salaName": cols[0].get_text(strip=True),
                "salaLocation": cols[1].get_text(strip=True)
            })
    return rooms
