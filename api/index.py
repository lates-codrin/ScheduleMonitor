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
async def get_timetable():
    
    
    response_data = [
    {
        "articleTitle": "Sesiune de Admitere Master",
        "articleDescription": "Încep înscrierile pentru programele de masterat, sesiunea de toamnă 2025.",
        "articleDate": "15.08.2025",
        "articleLink": "https://www.cs.ubbcluj.ro/admitere-master-toamna-2025/"
    },
    {
        "articleTitle": "Conferință Internațională de Informatică",
        "articleDescription": "Universitatea organizează o conferință internațională cu tema 'Inteligența Artificială în secolul XXI'.",
        "articleDate": "20.09.2025",
        "articleLink": "https://www.cs.ubbcluj.ro/conferinta-internationala-informatica-2025/"
    },
    {
        "articleTitle": "Burse de Excelență",
        "articleDescription": "Se anunță deschiderea sesiunii de aplicare pentru bursele de excelență academică.",
        "articleDate": "01.10.2025",
        "articleLink": "https://www.cs.ubbcluj.ro/burse-excelenta-2025/"
    },
        {
        "articleTitle": "Workshop Programare Avansată",
        "articleDescription": "Studenții sunt invitați la un workshop intensiv de programare avansată în C++.",
        "articleDate": "10.10.2025",
        "articleLink": "https://www.cs.ubbcluj.ro/workshop-programare-avansata-c-plus-plus/"
    },
    {
        "articleTitle": "Sesiune de Comunicări Științifice Studențești",
        "articleDescription": "Studenții sunt invitați să-și prezinte lucrările de cercetare în cadrul sesiunii anuale.",
        "articleDate": "25.10.2025",
        "articleLink": "https://www.cs.ubbcluj.ro/sesiune-comunicari-stiintifice-studentesti-2025/"
    },
    {
        "articleTitle": "Hackathon UBB",
        "articleDescription": "Se lansează ediția din acest an a hackathonului organizat de universitate.",
        "articleDate": "05.11.2025",
        "articleLink": "https://www.cs.ubbcluj.ro/hackathon-ubb-2025/"
    },
    {
        "articleTitle": "Ziua Porților Deschise",
        "articleDescription": "Viitorii studenți sunt invitați să viziteze facultatea în cadrul evenimentului anual.",
        "articleDate": "15.11.2025",
        "articleLink": "https://www.cs.ubbcluj.ro/ziua-portilor-deschise-2025/"
    },
    {
        "articleTitle": "Sesiune de Examene Restanțe",
        "articleDescription": "Se anunță perioada de desfășurare a sesiunii de examene restanțe.",
        "articleDate": "01.12.2025",
        "articleLink": "https://www.cs.ubbcluj.ro/sesiune-examene-restante-decembrie-2025/"
    },
    {
        "articleTitle": "Atelier de Robotică",
        "articleDescription": "Studenții sunt invitați să participe la un atelier practic de robotică.",
        "articleDate": "10.12.2025",
        "articleLink": "https://www.cs.ubbcluj.ro/atelier-robotica-2025/"
    },
        {
        "articleTitle": "Deadline Lucrări de Licență",
        "articleDescription": "Reamintim studenților că termenul limită pentru predarea lucrărilor de licență este 15.01.2026.",
        "articleDate": "12.01.2026",
        "articleLink": "https://www.cs.ubbcluj.ro/deadline-lucrari-licenta-ianuarie-2026/"
    },
    {
        "articleTitle": "Sesiune de Examene Licență",
        "articleDescription": "Se anunță perioada de desfășurare a sesiunii de examene de licență.",
        "articleDate": "20.01.2026",
        "articleLink": "https://www.cs.ubbcluj.ro/sesiune-examene-licenta-ianuarie-2026/"
    },
    {
        "articleTitle": "Program de Internship",
        "articleDescription": "Se deschide sesiunea de înscrieri pentru un program de internship în cadrul unei companii partenere.",
        "articleDate": "01.02.2026",
        "articleLink": "https://www.cs.ubbcluj.ro/program-internship-februarie-2026/"
    },
    {
        "articleTitle": "Concurs de Programare",
        "articleDescription": "Studenții sunt invitați să participe la un concurs de programare cu premii atractive.",
        "articleDate": "10.02.2026",
        "articleLink": "https://www.cs.ubbcluj.ro/concurs-programare-2026/"
    },
        {
        "articleTitle": "Sesiune de Admitere Licență",
        "articleDescription": "Încep înscrierile pentru programele de licență, sesiunea de vară 2026.",
        "articleDate": "15.07.2026",
        "articleLink": "https://www.cs.ubbcluj.ro/admitere-licenta-vara-2026/"
    },
    {
        "articleTitle": "Deadline Proiecte Restanțe",
        "articleDescription": "Reamintim studenților că termenul limită pentru predarea proiectelor restanțe este 10.08.2026.",
        "articleDate": "05.08.2026",
        "articleLink": "https://www.cs.ubbcluj.ro/deadline-proiecte-restante-august-2026/"
    }
]
    return response_data


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
