from sqlmodel import SQLModel, Field
from typing import Optional
import datetime

class SensorReading(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sensor: str
    value: float
    unit: str = ""
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

class DeviceState(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str
    last_action: str
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
