"""Account/CSRF/tenant smoke on an isolated migrated PostgreSQL QA database."""
import secrets,sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/api'))
from fastapi.testclient import TestClient
from sqlalchemy import delete,select
from app import main,security
from app.db import Session,engine,User,AuthSession,OAuthState,GmailConnection,MessageEvent,Event,Message,Job,Relationship,Audit
assert engine.dialect.name=='postgresql' and security.AUTH_MODE=='authenticated' and security.REGISTRATION_ENABLED
accounts=[]
try:
 a,b=TestClient(main.app,headers={'Origin':security.APP_ORIGIN}),TestClient(main.app,headers={'Origin':security.APP_ORIGIN})
 password=secrets.token_urlsafe(24)
 for client in [a,b]:
  result=client.post('/auth/register',json={'email':str(uuid.uuid4())+'@example.invalid','password':password})
  assert result.status_code==200,result.status_code
  info=result.json();accounts.append(info['user']['id']);client.headers['X-CSRF-Token']=info['csrf_token']
 assert a.post('/imports',json={'messages':[{'body':'Paid INR 88 at Cafe on 2026-10-01'}]}).status_code==200
 event=a.get('/events').json()[0]
 assert b.get('/events').json()==[] and b.get('/export').json()==[]
 assert b.patch('/events/'+event['id'],json={'field':'merchant','value':'Wrong owner','reason':'Synthetic QA'}).status_code==404
 assert a.delete('/data',headers={'X-CSRF-Token':'wrong'}).status_code==403
 assert a.post('/auth/logout').status_code==200 and a.get('/events').status_code==401
 print('PostgreSQL accounts, sessions, CSRF and tenant isolation: PASS')
finally:
 with Session() as s:
  owners=list(s.scalars(select(User.workspace_id).where(User.id.in_(accounts))))
  ids=list(s.scalars(select(Event.id).where(Event.owner.in_(owners))))
  s.execute(delete(MessageEvent).where(MessageEvent.event_id.in_(ids)))
  for model in [Audit,Relationship,Event,Message,Job]:s.execute(delete(model).where(model.owner.in_(owners)))
  for model,column in [(GmailConnection,GmailConnection.owner),(OAuthState,OAuthState.user_id),(AuthSession,AuthSession.user_id)]:s.execute(delete(model).where(column.in_(accounts)))
  s.execute(delete(User).where(User.id.in_(accounts)));s.commit()
