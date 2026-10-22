from fastapi import FastAPI, Form, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from .downloader import cancel_job, download_audio, jobs_lock, jobs, start_job
import uvicorn

app = FastAPI(title="Guardarol")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "guardarol"}

@app.post("/download")
async def download(url: str = Form(...), sync: bool = False):
    url = (url or "").strip()
    if not url:
        return JSONResponse(content={"status": "error", "message": "Pega una URL primero."})
    if sync:
        result = download_audio(url)
        return JSONResponse(content=result)
    job_id = start_job(url)
    return JSONResponse(content={"status": "queued", "job_id": job_id})

@app.get("/api/job/{job_id}")
async def job_status(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return JSONResponse(status_code=404, content={"status": "error", "message": "Job no encontrado."})
        return JSONResponse(content={k: v for k, v in job.items() if k != "cancelled"})

@app.post("/api/job/{job_id}/cancel")
async def job_cancel(job_id: str):
    if cancel_job(job_id):
        return JSONResponse(content={"status": "cancelled"})
    return JSONResponse(status_code=404, content={"status": "error", "message": "Job no encontrado o ya terminó."})

if __name__ == "__main__":
    from .config import settings
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
