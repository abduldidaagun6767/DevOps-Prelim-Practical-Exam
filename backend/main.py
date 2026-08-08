from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
from sqlmodel import SQLModel, Field, create_engine, Session, select
from .models import SensorReading, DeviceState
from .db import engine, init_db
from .broadcast import ConnectionManager
import asyncio
import datetime

app = FastAPI()

# serve static files
app.mount("/static", StaticFiles(directory="./static"), name="static")

manager = ConnectionManager()

class ReadingIn(BaseModel):
    sensor: str
    value: float
    unit: str = ""

class ActionIn(BaseModel):
    action: str
    payload: dict = {}

@app.on_event("startup")
def on_startup():
    init_db()

@app.post('/api/readings', status_code=201)
def post_reading(r: ReadingIn):
    reading = SensorReading(sensor=r.sensor, value=r.value, unit=r.unit, timestamp=datetime.datetime.utcnow())
    with Session(engine) as session:
        session.add(reading)
        session.commit()
        session.refresh(reading)
    # broadcast
    asyncio.create_task(manager.broadcast({"type": "reading", "data": reading.dict()}))
    return reading

@app.get('/api/readings/latest')
def latest_reading():
    with Session(engine) as session:
        stmt = select(SensorReading).order_by(SensorReading.timestamp.desc()).limit(1)
        res = session.exec(stmt).first()
        if not res:
            raise HTTPException(status_code=404, detail="No readings yet")
        return res

@app.get('/api/readings', response_model=List[SensorReading])
def readings(limit: int = 100):
    with Session(engine) as session:
        stmt = select(SensorReading).order_by(SensorReading.timestamp.desc()).limit(limit)
        return session.exec(stmt).all()

@app.post('/api/device/{device_id}/action')
def device_action(device_id: str, a: ActionIn):
    state = DeviceState(device_id=device_id, last_action=a.action, updated_at=datetime.datetime.utcnow())
    with Session(engine) as session:
        session.add(state)
        session.commit()
        session.refresh(state)
    asyncio.create_task(manager.broadcast({"type": "device", "data": state.dict()}))
    return {"status": "ok", "device": state}

@app.websocket('/ws')
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            # echo or handle incoming messages if needed
            await ws.send_text(f"echo: {data}")
    except WebSocketDisconnect:
        manager.disconnect(ws)

@app.get('/')
def root():
    return FileResponse('./static/index.html')
