import time
from fastapi import HTTPException
from sqlalchemy import select
from app import gmail, gmail_jobs
from app.db import GmailImportTask, GmailConnection, AuthSession
from test_security import env, client, account, connect, mock_provider

PARAMS={'after':'2026-10-01','before':'2026-10-15','limit':20,'consent':True}

def setup(env,monkeypatch):
 monkeypatch.setattr(gmail_jobs,'Session',env)
 c=client();info=account(c,'queue@example.invalid');mock_provider(monkeypatch);connect(c)
 return c,info

def test_queue_is_private_deduplicated_and_completes(env,monkeypatch):
 c,info=setup(env,monkeypatch)
 r=c.post('/connectors/gmail/imports',json=PARAMS);assert r.status_code==202,r.text
 task=r.json();assert task['status']=='queued' and 'parameters' not in task and 'session_hash' not in task
 assert c.post('/connectors/gmail/imports',json=PARAMS).json()['id']==task['id']
 other=client();account(other,'other@example.invalid')
 assert other.get('/connectors/gmail/imports/'+task['id']).status_code==404
 assert other.get('/connectors/gmail/imports/latest').json() is None
 assert gmail_jobs.run_once(env)
 finished=c.get('/connectors/gmail/imports/'+task['id']).json()
 assert finished['status']=='complete' and finished['result']['counts']['retained']==1
 assert c.get('/connectors/gmail/status').json()['last_success_at']
 assert not gmail_jobs.run_once(env)
 with env() as s:assert s.get(GmailImportTask,task['id']).parameters=={}
 # Retry same bounded window: no duplicate financial record.
 c.post('/connectors/gmail/imports',json=PARAMS);gmail_jobs.run_once(env)
 assert c.get('/connectors/gmail/imports/latest').json()['result']['counts']['reimported']==1


def test_retry_backoff_budget_and_restart_recovery(env,monkeypatch):
 c,_=setup(env,monkeypatch);task=c.post('/connectors/gmail/imports',json=PARAMS).json()
 def unavailable(*a,**k):raise HTTPException(502,'private provider detail must not escape')
 monkeypatch.setattr(gmail,'execute_import',unavailable)
 for attempt in range(1,4):
  with env() as s:
   t=s.get(GmailImportTask,task['id']);t.available_at=0;s.commit()
  assert gmail_jobs.run_once(env)
  state=c.get('/connectors/gmail/imports/'+task['id']).json()
  assert state['attempts']==attempt and 'private' not in state['error']
  if attempt<3:assert state['status']=='queued' and not gmail_jobs.run_once(env)
 assert state['status']=='failed'
 # A process can die after claiming; an expired lease is reclaimed but capped.
 new=c.post('/connectors/gmail/imports',json=PARAMS).json()
 with env() as s:
  t=s.get(GmailImportTask,new['id']);t.status='running';t.attempts=3;t.lease_until=0;s.commit()
 assert gmail_jobs.run_once(env)
 with env() as s:assert s.get(GmailImportTask,new['id']).status=='failed'


def test_logout_disconnect_and_erase_stop_pending_work(env,monkeypatch):
 c,info=setup(env,monkeypatch);task=c.post('/connectors/gmail/imports',json=PARAMS).json()
 c.post('/auth/logout');assert gmail_jobs.run_once(env)
 with env() as s:assert s.get(GmailImportTask,task['id']).status=='cancelled'
 # New account/session and connection are independent of the cancelled task.
 c=client();account(c,'erase@example.invalid');connect(c)
 task=c.post('/connectors/gmail/imports',json=PARAMS).json()
 c.delete('/data');assert not gmail_jobs.run_once(env)
 assert c.get('/connectors/gmail/imports/'+task['id']).status_code==404
 assert c.get('/events').json()==[]
 task=c.post('/connectors/gmail/imports',json=PARAMS).json();c.delete('/connectors/gmail/connection')
 gmail_jobs.run_once(env);assert c.get('/connectors/gmail/imports/'+task['id']).json()['status']=='cancelled'


def test_data_deletion_during_fetch_prevents_retention(env,monkeypatch):
 c,_=setup(env,monkeypatch);original=gmail.google
 def erase_during_fetch(method,url,**kwargs):
  if '/messages/' in url:assert c.delete('/data').status_code==200
  return original(method,url,**kwargs)
 monkeypatch.setattr(gmail,'google',erase_during_fetch)
 c.post('/connectors/gmail/imports',json=PARAMS);assert gmail_jobs.run_once(env)
 assert c.get('/events').json()==[] and c.get('/jobs').json()==[]


def test_active_lease_not_claimed_and_expired_lease_recovered(env,monkeypatch):
 c,_=setup(env,monkeypatch);task=c.post('/connectors/gmail/imports',json=PARAMS).json()
 with env() as s:
  t=s.get(GmailImportTask,task['id']);t.status='running';t.attempts=1;t.lease_until=int(time.time())+100;s.commit()
 assert not gmail_jobs.run_once(env)
 with env() as s:t=s.get(GmailImportTask,task['id']);t.lease_until=0;s.commit()
 assert gmail_jobs.run_once(env)
 assert c.get('/connectors/gmail/imports/'+task['id']).json()['status']=='complete'
