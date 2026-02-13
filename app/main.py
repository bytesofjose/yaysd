from fastapi import FastAPI, Form, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from .downloader import download_audio
import uvicorn

app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/download")
async def download(url: str = Form(...)):
    result = download_audio(url)
    return JSONResponse(content=result)

if __name__ == "__main__":
    from .config import settings
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
