from fastapi import FastAPI, WebSocket, HTTPException
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, DateTime
from pydantic import BaseModel, field_validator
from datetime import datetime
import json

# Конфігурація з config.py
from config import POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB

# Підключення до БД
DATABASE_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
engine = create_engine(DATABASE_URL)
metadata = MetaData()

# Оголошення таблиці
processed_agent_data = Table(
    "processed_agent_data",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("road_state", String),
    Column("x", Float),
    Column("y", Float),
    Column("z", Float),
    Column("latitude", Float),
    Column("longitude", Float),
    Column("timestamp", DateTime),
)

# Моделі Pydantic
class AccelerometerData(BaseModel):
    x: float
    y: float
    z: float

class GpsData(BaseModel):
    latitude: float
    longitude: float

class AgentData(BaseModel):
    accelerometer: AccelerometerData
    gps: GpsData
    timestamp: datetime

    @classmethod
    @field_validator('timestamp', mode='before')
    def check_timestamp(cls, value):
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            raise ValueError("Невірний формат часу. Очікується ISO 8601 (напр. 2023-10-05T12:00:00).")

class ProcessedAgentData(BaseModel):
    road_state: str
    agent_data: AgentData

class ProcessedAgentDataInDB(BaseModel):
    id: int
    road_state: str
    x: float
    y: float
    z: float
    latitude: float
    longitude: float
    timestamp: datetime

# Ініціалізація FastAPI
app = FastAPI()
subscriptions: set[WebSocket] = set()

# WebSocket
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    subscriptions.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        subscriptions.remove(websocket)

# CRUD-ендпоінти
@app.post("/processed_agent_data/")
async def create_processed_agent_data(data: list[ProcessedAgentData]):
    with engine.connect() as conn:
        for item in data:
            conn.execute(
                processed_agent_data.insert().values(
                    road_state=item.road_state,
                    x=item.agent_data.accelerometer.x,
                    y=item.agent_data.accelerometer.y,
                    z=item.agent_data.accelerometer.z,
                    latitude=item.agent_data.gps.latitude,
                    longitude=item.agent_data.gps.longitude,
                    timestamp=item.agent_data.timestamp,
                )
            )
        conn.commit()
    return {"message": "Дані успішно додані"}

@app.get("/processed_agent_data/", response_model=list[ProcessedAgentDataInDB])
def list_processed_agent_data():
    with engine.connect() as conn:
        result = conn.execute(processed_agent_data.select()).fetchall()
        return result

# Запуск сервера
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)