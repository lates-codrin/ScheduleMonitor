from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from bs4 import BeautifulSoup
import requests
import os
from dotenv import load_dotenv

from api.services.fetcher import extract_group_links, get_html
from api.services.parser import parse_timetable_from_url, parse_news, parse_rooms
from .config import *

load_dotenv()

app = FastAPI(docs_url="/orar/docs", openapi_url="/orar/openapi.json")
templates = Jinja2Templates(directory="templates")

# ==================== STATIC ROUTES ====================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/orar/{grupa}")
def get_timetable(grupa: int):
    groups = extract_group_links()
    if grupa not in groups:
        return {"Grupa": grupa, "Message": "Grupa nu a fost gasita.", "Code": -1}

    data = parse_timetable_from_url(groups[grupa], grupa)
    return {
        "Grupa": grupa,
        "Orar": data or [],
        "Code": 1 if data else 0
    }

@app.get("/news")
def get_news():
    try:
        html = get_html(NEWS_URL)
        return parse_news(html)
    except Exception as e:
        return {"error": str(e)}

@app.get("/rooms")
def get_rooms():
    try:
        html = get_html(ROOMS_URL)
        return parse_rooms(html)
    except Exception as e:
        return {"error": str(e)}

# ==================== LOGIN FLOW ====================
# Temporary Patch ; @15.04.2025 Iter1 ## Author: Codrin-Gabriel Lates

session_store = {}

@app.post("/start-login")
def start_login(user_id: str):
    try:
        session = requests.Session()
        login_url = "https://academicinfo.ubbcluj.ro/Default.aspx"
        
        resp = session.get(login_url)
        
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch the login page.")
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        recaptcha_div = soup.find("div", class_="g-recaptcha")
        if recaptcha_div is None:
            raise HTTPException(status_code=400, detail="ReCAPTCHA sitekey not found.")
        
        sitekey = recaptcha_div.get("data-sitekey")
        if not sitekey:
            raise HTTPException(status_code=400, detail="ReCAPTCHA sitekey is missing.")
        
        viewstate = soup.find("input", {"name": "__VIEWSTATE"})["value"]
        eventvalidation = soup.find("input", {"name": "__EVENTVALIDATION"})["value"]
        viewstategen = soup.find("input", {"name": "__VIEWSTATEGENERATOR"})["value"]
        
        session_store[user_id] = {
            "session": session,
            "viewstate": viewstate,
            "eventvalidation": eventvalidation,
            "viewstategen": viewstategen
        }
        
        return JSONResponse(content={"sitekey": sitekey})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/solve-captcha")
def solve_captcha(user_id: str, username: str, password: str, captcha_response: str):
    store = session_store.get(user_id)
    if not store:
        return JSONResponse(content={"error": "Session expired"}, status_code=400)

    session = store["session"]
    data = {
        "__VIEWSTATE": store["viewstate"],
        "__EVENTVALIDATION": store["eventvalidation"],
        "__VIEWSTATEGENERATOR": store["viewstategen"],
        "txtUsername": username,
        "txtPassword": password,
        "g-recaptcha-response": captcha_response,  # jus pass it to the uni
        "btnLogin": "Log in"
    }

    login_resp = session.post("https://academicinfo.ubbcluj.ro/Default.aspx", data=data)
    if "Note.aspx" not in login_resp.text and "Note" not in login_resp.url:
        return JSONResponse(content={"error": "Login failed"}, status_code=401)

    grades_resp = session.get("https://academicinfo.ubbcluj.ro/Note.aspx")
    soup = BeautifulSoup(grades_resp.content, 'html.parser')
    table = soup.find("table", {"id": "ctl00_ContentPlaceHolder1_gvNote"})
    rows = table.find("tbody").find_all("tr")

    grades = []
    for row in rows:
        cols = row.find_all("td")
        grades.append({
            "Nr Crt": cols[0].text.strip(),
            "An studiu": cols[1].text.strip(),
            "Semestru plan": cols[2].text.strip(),
            "Cod disciplina": cols[3].text.strip(),
            "Disciplina": cols[4].text.strip(),
            "Nota": cols[5].text.strip(),
            "Credite": cols[6].text.strip(),
            "Data promovarii": cols[7].text.strip()
        })

    return JSONResponse(content=grades)
