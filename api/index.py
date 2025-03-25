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
    global last_data, last_checked_time
    for group_nr in available_groups:
        new_data = fetch_timetable(group_nr)
        if new_data and (group_nr not in last_data or last_data[group_nr] != new_data):
            print(f"Changes detected for group {group_nr}:")
            print_diff(last_data.get(group_nr, ""), new_data)
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
    
    if grupa not in last_data:
        background_tasks.add_task(check_for_changes)
        last_data[grupa] = fetch_timetable(grupa)
        return {"Grupa": grupa, "Message": "Prima rulare.", "Orar": json.loads(last_data[grupa]), "Code": -1}
    
    new_data = last_data[grupa]
    last_seen = last_seen_data.get(grupa, "")
    changes_detected = last_seen and last_seen != new_data
    

    print_diff(last_seen, new_data)
    
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
