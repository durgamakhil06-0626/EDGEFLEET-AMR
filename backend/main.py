
import asyncio
import json
import math
import time
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).resolve().parent.parent
FRONTEND = BASE / "frontend"

app = FastAPI(title="EDGEFLEET Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/frontend", StaticFiles(directory=str(FRONTEND)), name="frontend")

SCENARIOS = {
    "normal": "3 autonomous robots · dynamic routes enabled",
    "choke": "Choke point conflict · local priority arbitration enabled",
    "blocked": "Blocked aisle · edge route replanning enabled",
    "failure": "AMR-02 failure · task handoff to AMR-03",
    "server": "Central server failure · P2P coordination continues",
}

PATHS = {
    "normal": {
        1: [(70,27),(62,27),(54,27),(46,27),(38,38),(30,49),(23,49),(30,60),(43,67),(56,67),(70,58),(82,49)],
        2: [(83,38),(76,38),(69,38),(61,38),(55,49),(61,58),(70,58),(78,58),(86,70)],
        3: [(82,49),(74,49),(66,49),(58,49),(50,60),(42,67),(50,76),(63,76),(76,70),(86,70)],
    },
    "choke": {
        1: [(70,27),(62,27),(55,30),(48,38),(42,49),(35,49),(42,49),(50,49),(58,49),(70,49)],
        2: [(83,38),(76,38),(68,38),(60,38),(53,49),(46,49),(53,49),(60,38),(70,38)],
        3: [(82,49),(74,49),(66,49),(58,49),(53,49),(46,49),(39,49),(31,49),(23,49)],
    },
    "blocked": {
        1: [(70,27),(62,27),(54,27),(46,27),(38,38),(31,49),(25,60),(35,70),(48,76),(62,76),(76,70)],
        2: [(83,38),(76,38),(69,38),(62,38),(55,58),(64,67),(73,76),(85,76)],
        3: [(82,49),(74,49),(66,49),(58,49),(50,60),(43,70),(35,76),(25,76)],
    },
    "failure": {
        1: [(70,27),(62,27),(54,27),(46,38),(38,49),(46,58),(58,67),(70,67),(82,58)],
        2: [(83,38),(76,38),(69,38),(62,49),(55,58),(48,67),(40,76),(28,76)],
        3: [(82,49),(74,49),(66,49),(58,58),(50,67),(58,76),(70,76),(82,70)],
    },
    "server": {
        1: [(70,27),(62,27),(54,27),(46,38),(38,49),(30,49),(38,60),(50,67),(62,67),(76,58)],
        2: [(83,38),(76,38),(69,38),(62,49),(55,49),(62,58),(70,67),(82,67)],
        3: [(82,49),(74,49),(66,49),(58,49),(50,58),(42,67),(30,67),(22,58)],
    },
}

class Fleet:
    def __init__(self):
        self.running = False
        self.paused = False
        self.time = 0.0
        self.speed = 1.0
        self.mode = "ai"
        self.scenario = "normal"
        self.server_online = True
        self.collisions = 0
        self.robots = {
            1: {"x":70.0,"y":27.0,"battery":85,"status":"MOVING","task":"TASK-101","speed":1.2},
            2: {"x":83.0,"y":38.0,"battery":72,"status":"WAITING","task":"TASK-102","speed":0.8},
            3: {"x":82.0,"y":49.0,"battery":91,"status":"REROUTING","task":"TASK-104","speed":1.0},
        }
        self.clients: List[WebSocket] = []
        self._last = time.monotonic()
        self._last_event = 0

    def reset(self):
        self.running = False
        self.paused = False
        self.time = 0.0
        self.speed = 1.0
        self.mode = "ai"
        self.scenario = "normal"
        self.server_online = True
        self.collisions = 0
        self.robots = {
            1: {"x":70.0,"y":27.0,"battery":85,"status":"MOVING","task":"TASK-101","speed":1.2},
            2: {"x":83.0,"y":38.0,"battery":72,"status":"WAITING","task":"TASK-102","speed":0.8},
            3: {"x":82.0,"y":49.0,"battery":91,"status":"REROUTING","task":"TASK-104","speed":1.0},
        }

    def interp(self, pts, t):
        if t >= 1: return pts[-1]
        n = len(pts)-1
        p = max(0.0,t)*n
        i = min(n-1,int(p))
        f = p-i
        ax,ay=pts[i]; bx,by=pts[i+1]
        return ax+(bx-ax)*f, ay+(by-ay)*f

    def update(self, dt):
        if not self.running or self.paused:
            return
        self.time += dt*self.speed
        path = PATHS[self.scenario]
        rates = {1:0.045,2:0.038,3:0.052}
        for i,r in self.robots.items():
            if self.scenario=="failure" and i==2 and self.time>4:
                r["x"],r["y"]=83,38
                r["status"]="FAILED"
                r["speed"]=0.0
                r["battery"]=max(0,int(72-(self.time-4)*0.9))
                continue
            x,y=self.interp(path[i], (self.time*rates[i])%1)
            r["x"],r["y"]=x,y
            r["battery"]=max(20,int(r["battery"] - dt*self.speed*0.05))
            r["speed"]={1:1.2,2:0.8,3:1.0}[i]
            r["status"]="MOVING"

        if self.scenario=="choke":
            self.robots[2]["status"] = "WAITING" if self.mode=="ai" else "BLOCKED"
            self.robots[2]["speed"] = 0.0
        elif self.scenario=="blocked":
            self.robots[1]["status"]="REROUTING"
        elif self.scenario=="failure":
            self.robots[3]["status"]="HANDOFF" if self.time>8 else "REROUTING"
            if self.time>8:
                self.robots[3]["task"]="TASK-102"
        elif self.scenario=="server" and not self.server_online:
            for r in self.robots.values():
                if r["status"]!="FAILED":
                    r["status"]="P2P MOVING"

    def state(self):
        risk=0
        decision="All trajectories safe"
        if self.scenario=="choke":
            risk=18+round(abs(math.sin(self.time))*12) if self.mode=="ai" else 76
            decision="AMR-02 yields at choke point" if self.mode=="ai" else "Stop-and-Wait queue forming"
        elif self.scenario=="blocked":
            risk=11
            decision="Blocked aisle detected · route replanned at edge"
        elif self.scenario=="failure":
            risk=8
            decision="Task-102 handed to AMR-03" if self.time>8 else "AMR-02 heartbeat lost"
        elif self.scenario=="server":
            risk=5
            decision="Central coordination available" if self.server_online else "P2P continues without central server"
        return {
            "time":self.time, "running":self.running, "paused":self.paused,
            "mode":self.mode, "scenario":self.scenario,
            "server_online":self.server_online, "links":3,
            "collisions":self.collisions, "risk":risk, "decision":decision,
            "robots":[{"id":i,**r} for i,r in self.robots.items()],
            "scenario_text":SCENARIOS[self.scenario],
            "task_text":"TASKS 101 / 102 / 104" if self.scenario!="failure" or self.time<=8 else "TASKS 101 / 102(HANDOFF) / 104",
        }

fleet=Fleet()

@app.get("/")
async def index():
    return FileResponse(FRONTEND/"index.html")

@app.get("/api/health")
async def health():
    return {"status":"ok","service":"EDGEFLEET","websocket":"/ws"}

@app.get("/api/state")
async def api_state():
    return fleet.state()

async def broadcast(message):
    dead=[]
    for ws in fleet.clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in fleet.clients: fleet.clients.remove(ws)

async def simulator():
    fleet._last=time.monotonic()
    while True:
        now=time.monotonic()
        dt=min(now-fleet._last,0.25)
        fleet._last=now
        before=fleet.time
        fleet.update(dt)
        if fleet.running and not fleet.paused and int(fleet.time*10)%2==0:
            await broadcast({"type":"state","data":fleet.state()})
        await asyncio.sleep(0.08)

@app.on_event("startup")
async def startup():
    asyncio.create_task(simulator())

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    fleet.clients.append(ws)
    await ws.send_json({"type":"state","data":fleet.state()})
    try:
        while True:
            msg=await ws.receive_json()
            action=msg.get("action")
            if action=="start":
                fleet.running=True; fleet.paused=False
                await broadcast({"type":"event","message":"Fleet simulation started · backend is driving robot state","level":"ai","time":fleet.time})
            elif action=="pause":
                fleet.paused=not fleet.paused
                await broadcast({"type":"event","message":"Simulation "+("paused" if fleet.paused else "resumed"),"level":"warn","time":fleet.time})
            elif action=="reset":
                fleet.reset()
                await broadcast({"type":"event","message":"Fleet reset to initial state","level":"ai","time":0})
            elif action=="speed":
                fleet.speed=float(msg.get("value",1))
                await broadcast({"type":"event","message":f"Backend simulation speed set to {fleet.speed}×","level":"ai","time":fleet.time})
            elif action=="mode":
                fleet.mode=msg.get("value","ai")
                await broadcast({"type":"event","message":"Decentralized Edge AI enabled" if fleet.mode=="ai" else "Stop-and-Wait baseline enabled","level":"ai" if fleet.mode=="ai" else "warn","time":fleet.time})
            elif action=="scenario":
                value=msg.get("value","normal")
                if value in PATHS:
                    fleet.scenario=value
                    fleet.time=0
                    fleet.running=True
                    fleet.paused=False
                    await broadcast({"type":"event","message":SCENARIOS[value],"level":"warn","time":fleet.time})
            elif action=="server_toggle":
                fleet.server_online=not fleet.server_online
                await broadcast({"type":"event","message":"Central server restored" if fleet.server_online else "Central server lost · fleet switched to P2P","level":"warn","time":fleet.time})
            elif action=="state":
                await ws.send_json({"type":"state","data":fleet.state()})
    except WebSocketDisconnect:
        if ws in fleet.clients: fleet.clients.remove(ws)
    except Exception:
        if ws in fleet.clients: fleet.clients.remove(ws)
