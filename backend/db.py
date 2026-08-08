from sqlmodel import create_engine, SQLModel
from .models import SensorReading, DeviceState
import os

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///./data.db')
engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)
