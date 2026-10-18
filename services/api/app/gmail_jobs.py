"""Durable, user-requested Gmail work. Queue stores metadata, never raw mail."""
import time
from types import SimpleNamespace
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, update, or_, and_
from sqlalchemy.exc import IntegrityError
from .db import Session, GmailImportTask, GmailConnection, User, AuthSession, uid, now
from .schema import GmailImport
from . import gmail, security

router=APIRouter(prefix='/connectors/gmail/imports',tags=['Gmail background imports'])
LEASE_SECONDS=1200


def public_task(task):
 return {k:getattr(task,k) for k in ['id','status','attempts','created_at','finished_at','result','error']}

@router.post('',status_code=202)
def enqueue(payload:GmailImport,request:Request):
 gmail.require_account(request);gmail.config()
 with Session() as s:
  connection=s.get(GmailConnection,request.state.user.id)
  if not connection:raise HTTPException(409,'Connect Gmail before importing.')
  existing=s.scalar(select(GmailImportTask).where(GmailImportTask.active_key==request.state.user.id))
  if existing:return public_task(existing)
  security.throttle(s,'gmail-queue:'+request.state.user.id,10)
  task=GmailImportTask(id=uid(),user_id=request.state.user.id,session_hash=request.state.session.token_hash,generation=connection.generation,active_key=request.state.user.id,parameters=payload.model_dump(mode='json'),status='queued',attempts=0,available_at=int(time.time()),lease_until=0)
  s.add(task)
  try:s.commit()
  except IntegrityError:
   s.rollback();raise HTTPException(409,'An import is already queued for this account.') from None
  return public_task(task)

@router.get('/latest')
def latest(request:Request):
 gmail.require_account(request)
 with Session() as s:
  task=s.scalar(select(GmailImportTask).where(GmailImportTask.user_id==request.state.user.id).order_by(GmailImportTask.created_at.desc()).limit(1))
  return public_task(task) if task else None

@router.get('/{task_id}')
def get_task(task_id:str,request:Request):
 gmail.require_account(request)
 with Session() as s:
  task=s.get(GmailImportTask,task_id)
  if not task or task.user_id!=request.state.user.id:raise HTTPException(404,'Import not found.')
  return public_task(task)


def run_once(factory=None):
 factory=factory or Session;clock=int(time.time())
 with factory() as s:
  eligible=or_(and_(GmailImportTask.status=='queued',GmailImportTask.available_at<=clock),and_(GmailImportTask.status=='running',GmailImportTask.lease_until<=clock))
  task=s.scalar(select(GmailImportTask).where(eligible).order_by(GmailImportTask.created_at).limit(1))
  if task is None:return False
  task_id=task.id
  if task.attempts>=3:
   s.execute(update(GmailImportTask).where(GmailImportTask.id==task_id,eligible,GmailImportTask.attempts>=3).values(status="failed",error="Import stopped after repeated interruptions. Start a new import.",active_key=None,parameters={},finished_at=now()));s.commit();return True
  claimed=s.execute(update(GmailImportTask).where(GmailImportTask.id==task_id,eligible).values(status='running',lease_until=clock+LEASE_SECONDS,attempts=GmailImportTask.attempts+1)).rowcount
  s.commit()
  if not claimed:return False
  s.expire_all();task=s.get(GmailImportTask,task_id)
  attempt=task.attempts
  user=s.get(User,task.user_id);session=s.get(AuthSession,task.session_hash);connection=s.get(GmailConnection,task.user_id)
  allowed=bool(user and user.active and session and session.user_id==user.id and session.expires_at>clock and session.last_seen_at+security.IDLE_SECONDS>clock and connection and connection.generation==task.generation)
  if not allowed:
   task.status='cancelled';task.error='Sign in and reconnect Gmail before starting another import.';task.active_key=None;task.parameters={};task.finished_at=now();s.commit();return True
  request=SimpleNamespace(state=SimpleNamespace(user=user,session=session,owner=user.workspace_id))
  parameters=task.parameters;generation=task.generation
 try:
  result=gmail.execute_import(GmailImport.model_validate(parameters),request,expected_generation=generation)
  status,error='complete',None
 except HTTPException as exc:
  result=None;status='queued' if exc.status_code in (429,502,503) and attempt<3 else 'failed'
  error='Gmail is temporarily unavailable. Retrying.' if status=='queued' else 'Import stopped. Check your Gmail connection and start again.'
 except Exception:
  result=None;status='failed';error='Import stopped. Check your connection and start again.'
 with factory() as s:
  # A stale worker cannot overwrite a later claim's status.
  values={'status':status,'result':result,'error':error,'lease_until':0,'available_at':int(time.time())+30*attempt}
  if status!='queued':values.update(active_key=None,parameters={},finished_at=now())
  s.execute(update(GmailImportTask).where(GmailImportTask.id==task_id,GmailImportTask.attempts==attempt,GmailImportTask.status=='running').values(**values));s.commit()
 return True
