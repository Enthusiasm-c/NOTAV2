from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, func
from app.db import Base
from enum import Enum as PyEnum

class FSMState(PyEnum):
    waiting_photo = "waiting_photo"
    reviewing = "reviewing"
    editing = "editing"
    confirming = "confirming"
    done = "done"

class InvoiceState(Base):
    __tablename__ = "invoice_state"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String(64), nullable=False, index=True)
    json_draft = Column(Text, nullable=True)  # текущий черновик (JSON)
    state = Column(Enum(FSMState), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
