import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
from urllib.parse import urljoin
from fastapi import FastAPI, BackgroundTasks
import re
BASE_URL = "https://webfmi.vercel.app/"
app = FastAPI(docs_url="/api/py/docs", openapi_url="/api/py/openapi.json")

last_data = {}
last_seen_data = {}
last_checked_time = {}
available_groups = set()

pd.set_option('display.max_columns', None)
pd.set_option('display.max_colwidth', 0)
pd.set_option('display.max_rows', 999)
pd.set_option('display.width', None)

def get_all_html_links(url):
    """Fetches all .html links from the given page."""
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to access {url}")
        return []
    
    soup = BeautifulSoup(response.text, "html.parser")
    links = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.endswith(".html"):
            full_url = urljoin(BASE_URL, href)
            links.append(full_url)
    
    return links

def extract_group_numbers(url):
    """Extracts group numbers from the given HTML page."""
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to access {url}")
        return []
    
    soup = BeautifulSoup(response.text, "html.parser")
    group_numbers = set()
    
    for header in soup.find_all("1"):
        match = re.search(r"Grupa\s*(\d+)", header.text)
        if match:
            group_numbers.add(int(match.group(1)))
    
    return list(group_numbers)

def scan_all_pages():
    """Scans all HTML pages and extracts group numbers."""
    global available_groups
    main_page_links = get_all_html_links(BASE_URL)
    all_group_numbers = set()
    
    for page in main_page_links:
        print(f"Scanning {page}...")
        groups = extract_group_numbers(page)
        all_group_numbers.update(groups)
        time.sleep(10)
    
    available_groups = all_group_numbers

def fetch_timetable(group_nr: int):
    """Scrapes the timetable for a specific group number."""
    url = 'https://webfmi.vercel.app/'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    headers = soup.find_all('h1')
    target_header = next((header for header in headers if f"Grupa {group_nr}" in header.text), None)
    
    if not target_header:
        print(f"Timetable for group {group_nr} not found.")
        return None

    table = target_header.find_next('table')
    df = pd.DataFrame(columns=['Ziua', 'Orele', 'Sala', 'Frecventa', 'Formatia', 'Tipul', 'Disciplina', 'CD'])
    
    if table:
        rows = table.find_all('tr')
        for row in rows:
            columns = row.find_all('td')
            if columns:
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
    """Runs in the background, checking for updates."""
    global last_data, last_checked_time
    for group_nr in available_groups:
        new_data = fetch_timetable(group_nr)
        if group_nr not in last_data or last_data[group_nr] != new_data:
            last_data[group_nr] = new_data
            last_checked_time[group_nr] = time.strftime("%Y-%m-%d %H:%M:%S")

@app.on_event("startup")
def startup_event():
    scan_all_pages()

@app.get("/")
async def get_home():
    return "Schedule Monitor front page. Try /orar/group_number!"

@app.get("/orar/{grupa}")
async def get_timetable(grupa: int, background_tasks: BackgroundTasks):
    """Returns the timetable and triggers an update in the background."""
    if grupa not in available_groups:
        return {"Grupa": grupa, "Message": "Grupa nu a fost gasita.", "Code": -1}

    if grupa not in last_data:
        background_tasks.add_task(check_for_changes)
        return {"Grupa": grupa, "Message": "Nu exista date disponibile.", "Code": -1}

    new_data = last_data[grupa]
    last_seen = last_seen_data.get(grupa, "")
    
    changes_detected = last_seen and last_seen != new_data

    response_data = {
        "Grupa": grupa,
        "Message": "Modificari gasite!" if changes_detected else "Nu exista modificari.",
        "Ultima verificare": last_checked_time.get(grupa, "N/A"),
        "Orar": json.loads(new_data),
        "Code": 1 if changes_detected else 0
    }

    last_seen_data[grupa] = new_data
    background_tasks.add_task(check_for_changes)
    return response_data

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
