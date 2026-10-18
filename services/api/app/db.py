import os, uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, JSON, ForeignKey, UniqueConstraint, Integer, Boolean, BigInteger
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
class User(Base):
    __tablename__='users'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    gmail_epoch: Mapped[int]=mapped_column(Integer,default=0)
    workspace_id: Mapped[str]=mapped_column(String,unique=True,default=uid)
    email: Mapped[str]=mapped_column(String,unique=True,index=True)
    password_hash: Mapped[str]=mapped_column(String)
    active: Mapped[bool]=mapped_column(Boolean,default=True)
    created_at: Mapped[str]=mapped_column(String,default=now)
class AuthSession(Base):
    __tablename__='auth_sessions'
    token_hash: Mapped[str]=mapped_column(String,primary_key=True)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    csrf_token: Mapped[str]=mapped_column(String)
    expires_at: Mapped[int]=mapped_column(BigInteger)
    last_seen_at: Mapped[int]=mapped_column(BigInteger)
class RateLimit(Base):
    __tablename__='rate_limits'
    key: Mapped[str]=mapped_column(String,primary_key=True)
    attempts: Mapped[int]=mapped_column(Integer)
    expires_at: Mapped[int]=mapped_column(BigInteger,index=True)
class OAuthState(Base):
    __tablename__='oauth_states'
    state_hash: Mapped[str]=mapped_column(String,primary_key=True)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    session_hash: Mapped[str]=mapped_column(String)
    connection_epoch: Mapped[int]=mapped_column(Integer,default=0)
    verifier_encrypted: Mapped[str]=mapped_column(String)
    expires_at: Mapped[int]=mapped_column(BigInteger,index=True)
class GmailConnection(Base):
    __tablename__='gmail_connections'
    owner: Mapped[str]=mapped_column(ForeignKey('users.id'),primary_key=True)
    generation: Mapped[str]=mapped_column(String,default=uid)
    email: Mapped[str]=mapped_column(String)
    tokens_encrypted: Mapped[str]=mapped_column(String)
    expires_at: Mapped[int]=mapped_column(BigInteger)
    locked_until: Mapped[int]=mapped_column(BigInteger,default=0)
    last_success_at: Mapped[str | None]=mapped_column(String,nullable=True)
    created_at: Mapped[str]=mapped_column(String,default=now)
DATABASE_URL=os.getenv('DATABASE_URL','sqlite:///./proofpay.db')
engine=create_engine(DATABASE_URL,connect_args={'check_same_thread':False} if DATABASE_URL.startswith('sqlite') else {})
Session=sessionmaker(engine,expire_on_commit=False)

class GmailImportTask(Base):
    __tablename__='gmail_import_tasks'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    session_hash: Mapped[str]=mapped_column(String)
    generation: Mapped[str]=mapped_column(String)
    active_key: Mapped[str | None]=mapped_column(String,unique=True,nullable=True)
    parameters: Mapped[dict]=mapped_column(JSON)
    status: Mapped[str]=mapped_column(String,default='queued')
    attempts: Mapped[int]=mapped_column(Integer,default=0)
    available_at: Mapped[int]=mapped_column(BigInteger,default=0)
    lease_until: Mapped[int]=mapped_column(BigInteger,default=0)
    result: Mapped[dict | None]=mapped_column(JSON,nullable=True)
    error: Mapped[str | None]=mapped_column(String,nullable=True)
    created_at: Mapped[str]=mapped_column(String,default=now)
    finished_at: Mapped[str | None]=mapped_column(String,nullable=True)
