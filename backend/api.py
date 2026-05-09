import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from backend.core import Spoofer

class JobRequest(BaseModel):
    path: str = ""
    mode: str = ""

class Progress(BaseModel):
    stat: str
    cur: int
    tot: int
    msg: str

class Response(BaseModel):
    ok: bool
    msg: str = ""

class Manager:
    def __init__(self):
        self.spoofer = Spoofer()
        self.state = Progress(stat="idle", cur=0, tot=0, msg="")

    def _callback(self, cur, tot, old, result):
        self.state.cur = cur
        self.state.tot = tot
        self.state.msg = f"{old} -> {result}".lower()
        self.state.stat = "run"

    def run_reup(self, path, mode):
        self.state.stat = "run"
        ok, msg = self.spoofer.reup(path, mode, self._callback)
        self.state.stat = "done" if ok else "err"
        self.state.msg = msg

    def run_dump(self, path):
        self.state.stat = "run"
        ok, msg = self.spoofer.dump(path, self._callback)
        self.state.stat = "done" if ok else "err"
        self.state.msg = msg

manager = Manager()

app = FastAPI()
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ui_dir = os.path.join(base_dir, "ui")
index_path = os.path.join(ui_dir, "index.html")

@app.get("/", response_class=FileResponse)
async def home():
    return index_path

@app.get("/state", response_model=Progress)
async def get_state():
    return manager.state

@app.post("/start", response_model=Response)
async def start_reup(request: JobRequest, background: BackgroundTasks):
    if not request.path:
        raise HTTPException(status_code=400, detail="missing path")

    if not os.path.exists(request.path):
        raise HTTPException(status_code=400, detail="file not found")

    manager.state.cur = 0
    manager.state.tot = 0
    background.add_task(manager.run_reup, request.path, request.mode)
    return Response(ok=True)

@app.post("/dump", response_model=Response)
async def start_dump(request: JobRequest, background: BackgroundTasks):
    if not request.path:
        raise HTTPException(status_code=400, detail="missing path")

    if not os.path.exists(request.path):
        raise HTTPException(status_code=400, detail="file not found")

    manager.state.cur = 0
    manager.state.tot = 0
    background.add_task(manager.run_dump, request.path)
    return Response(ok=True)

app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
