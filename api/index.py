import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
from urllib.parse import urljoin
from fastapi import FastAPI, BackgroundTasks
import re
import difflib

BASE_URL = "https://webfmi.vercel.app/"
app = FastAPI(docs_url="/orar/docs", openapi_url="/orar/openapi.json")

last_data = {}
last_seen_data = {}
last_checked_time = {}
available_groups = {}

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', 999)
pd.set_option('display.width', None)

def print_diff(old, new):
    """Prints differences between old and new timetable data."""
    old_lines = json.dumps(json.loads(old), indent=4).splitlines() if old else []
    new_lines = json.dumps(json.loads(new), indent=4).splitlines()
    diff = difflib.unified_diff(old_lines, new_lines, lineterm='')
    print("\n".join(diff))

def get_all_html_links(url):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to access {url}")
        return []
    
    soup = BeautifulSoup(response.text, "html.parser")
    return [urljoin(BASE_URL, link["href"]) for link in soup.find_all("a", href=True) if link["href"].endswith(".html")]

def extract_group_numbers(url):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to access {url}")
        return {}
    
    soup = BeautifulSoup(response.text, "html.parser")
    return {int(match.group(1)): url for header in soup.find_all("h1") if (match := re.search(r"Grupa\s*(\d+)", header.text))}

def scan_all_pages():
    global available_groups
    print("Scanning all timetable pages...")
    available_groups = {group: url for page in get_all_html_links(BASE_URL) for group, url in extract_group_numbers(page).items()}
    print("Finished scanning timetable pages.")

@app.get("/rescan")
def rescan():
    scan_all_pages()
    return {"Message": "Rescan completed.", "Available groups": available_groups}

def fetch_timetable(group_nr: int):
    if group_nr not in available_groups:
        print(f"Group {group_nr} not found in available timetable pages.")
        return None
    
    url = available_groups[group_nr]
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    target_header = next((header for header in soup.find_all('h1') if f"Grupa {group_nr}" in header.text), None)
    
    if not target_header:
        print(f"Timetable for group {group_nr} not found on {url}.")
        return None
    
    table = target_header.find_next('table')
    df = pd.DataFrame(columns=['Ziua', 'Orele', 'Sala', 'Frecventa', 'Formatia', 'Tipul', 'Disciplina', 'CD'])
    
    if table:
        rows = table.find_all('tr')
        for row in rows:
            columns = row.find_all('td')
            if len(columns) >= 8:
                df = df._append({
                    'Ziua': columns[0].text.strip(),
                    'Orele': columns[1].text.strip(),
                    'Sala': columns[3].text.strip(),
                    'Frecventa': columns[2].text.strip(),
                    'Formatia': columns[4].text.strip(),
                    'Tipul': columns[5].text.strip(),
                    'Disciplina': columns[6].text.strip(),
                    'CD': columns[7].text.strip()
                }, ignore_index=True)
    
    return df.to_json(orient="records")

def check_for_changes():
    global last_data, last_checked_time, last_seen_data

    for group_nr in available_groups:
        new_data = fetch_timetable(group_nr)

        if new_data:
            if group_nr not in last_data:
                print(f"Initial data fetched for group {group_nr}")
            elif last_data[group_nr] != new_data:
                print(f"Changes detected for group {group_nr}")
            
            last_data[group_nr] = new_data
            last_checked_time[group_nr] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    print("A fetch request has been performed at", time.strftime("%Y-%m-%d %H:%M:%S"))


@app.get("/")
async def get_home():
    return "Schedule Monitor front page. Try /orar/group_number!"

@app.get("/orar/{grupa}")
async def get_timetable(grupa: int, background_tasks: BackgroundTasks):
    if not available_groups:
        scan_all_pages()
    
    if grupa not in available_groups:
        return {"Grupa": grupa, "Message": "Grupa nu a fost gasita.", "Code": -1}

    # Ensure we have at least one scan before returning a response
    if grupa not in last_data:
        background_tasks.add_task(check_for_changes)
        return {"Grupa": grupa, "Message": "In curs de verificare...", "Code": -1}
    
    new_data = last_data.get(grupa, "")
    last_seen = last_seen_data.get(grupa, "")
    changes_detected = last_seen and last_seen != new_data
    
    response_data = {
        "Grupa": grupa,
        "Message": "Modificari gasite!" if changes_detected else "Nu exista modificari.",
        "Ultima verificare": last_checked_time.get(grupa, "N/A"),
        "Orar": json.loads(new_data) if new_data else [],
        "Code": 1 if changes_detected else 0
    }

    last_seen_data[grupa] = new_data
    background_tasks.add_task(check_for_changes)  # Schedule a check for next time
    return response_data

@app.get("/news")
async def get_news():
    url = "https://www.cs.ubbcluj.ro/anunturi/anunturi-studenti/"
    response = requests.get(url)
    if response.status_code != 200:
        return {"error": "Failed to fetch news"}

    soup = BeautifulSoup(response.text, 'html.parser')
    post_elements = soup.find_all("div", class_="post-box")

    articles = []

    for post in post_elements:
        title_tag = post.find("h2", class_="title").find("a")
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        link = title_tag.get("href")

        date_tag = post.find("span", class_="meta_date")
        date = date_tag.get_text(strip=True) if date_tag else "N/A"

        description_tag = post.find("div", class_="entry")
        full_description = description_tag.get_text(strip=True) if description_tag else ""

        # Try to find image src inside the entry div
        img_tag = description_tag.find("img") if description_tag else None
        image_url = img_tag.get("src") if img_tag else None

        articles.append({
            "articleTitle": title,
            "articleDescription": full_description,
            "articleDate": date,
            "articleLink": link,
            "articleImage": image_url  # Can be None
        })

    return articles




if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
