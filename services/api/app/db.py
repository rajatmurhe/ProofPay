import os, uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc).isoformat()
class Base(DeclarativeBase): pass
class Job(Base):
    __tablename__='jobs'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    owner: Mapped[str]=mapped_column(String,index=True)
    status: Mapped[str]=mapped_column(String,default='processing')
    counts: Mapped[dict]=mapped_column(JSON,default=dict)
    created_at: Mapped[str]=mapped_column(String,default=now)
class Message(Base):
    __tablename__='messages'
    __table_args__=(UniqueConstraint('owner','fingerprint'),)
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    owner: Mapped[str]=mapped_column(String,index=True)
    fingerprint: Mapped[str]=mapped_column(String)
    source: Mapped[str]=mapped_column(String)
    received_at: Mapped[str | None]=mapped_column(String,nullable=True)
    job_id: Mapped[str]=mapped_column(ForeignKey('jobs.id'))
    evidence: Mapped[list]=mapped_column(JSON,default=list)
    mode: Mapped[str]=mapped_column(String)
class Event(Base):
    __tablename__='events'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    owner: Mapped[str]=mapped_column(String,index=True)
    data: Mapped[dict]=mapped_column(JSON)
class MessageEvent(Base):
    __tablename__='message_events'
    message_id: Mapped[str]=mapped_column(ForeignKey('messages.id'),primary_key=True)
    event_id: Mapped[str]=mapped_column(ForeignKey('events.id'),primary_key=True)
class Relationship(Base):
    __tablename__='relationships'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    owner: Mapped[str]=mapped_column(String,index=True)
    left_id: Mapped[str]=mapped_column(ForeignKey('events.id'))
    right_id: Mapped[str]=mapped_column(ForeignKey('events.id'))
    kind: Mapped[str]=mapped_column(String)
    status: Mapped[str]=mapped_column(String)
    reason: Mapped[str]=mapped_column(String)
class Audit(Base):
    __tablename__='corrections'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    owner: Mapped[str]=mapped_column(String,index=True)
    event_id: Mapped[str]=mapped_column(String)
    data: Mapped[dict]=mapped_column(JSON)
    created_at: Mapped[str]=mapped_column(String,default=now)
DATABASE_URL=os.getenv('DATABASE_URL','sqlite:///./proofpay.db')
engine=create_engine(DATABASE_URL,connect_args={'check_same_thread':False} if DATABASE_URL.startswith('sqlite') else {})
Session=sessionmaker(engine,expire_on_commit=False)
