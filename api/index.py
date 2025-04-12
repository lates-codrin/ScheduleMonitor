from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from api.services.fetcher import extract_group_links, get_html
from api.services.parser import parse_timetable_from_url, parse_news, parse_rooms

from .config import *

app = FastAPI(docs_url="/orar/docs", openapi_url="/orar/openapi.json")
templates = Jinja2Templates(directory="templates")

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
