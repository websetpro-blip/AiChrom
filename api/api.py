from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from . import engine

app = FastAPI(title="AiChrome API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],
    allow_methods=["*"], 
    allow_headers=["*"]
)

@app.get("/health")
def health(): 
    return {"ok": True}

@app.get("/profiles")
def profiles(): 
    return engine.load()

@app.post("/profiles")
def create(): 
    return engine.create_profile()

@app.post("/profiles/{pid}/start")
def start(pid: str):
    items = engine.load()
    p = next((x for x in items if x["id"] == pid), None)
    if not p: 
        raise HTTPException(404, "Profile not found")
    engine.start_profile(p)
    p["active"] = True
    engine.save(items)
    return {"ok": True}

@app.post("/profiles/{pid}/selftest")
def selftest(pid: str):
    items = engine.load()
    p = next((x for x in items if x["id"] == pid), None)
    if not p: 
        raise HTTPException(404, "Profile not found")
    res = engine.selftest(p)
    return res
