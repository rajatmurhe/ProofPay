import base64
import json
import os
import subprocess
import time
from urllib.parse import urlparse, parse_qs
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app import main, security, gmail
from app.db import Base, User, AuthSession, Event, GmailConnection, OAuthState, Message, Job

PASSWORD='Synthetic password 729!'

@pytest.fixture
def env(monkeypatch):
 engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
 Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
 monkeypatch.setattr(main,'Session',factory);monkeypatch.setattr(gmail,'Session',factory)
 monkeypatch.setattr(security,'AUTH_MODE','authenticated');monkeypatch.setattr(security,'REGISTRATION_ENABLED',True)
 monkeypatch.setattr(security,'APP_ORIGIN','http://127.0.0.1:3017')
 monkeypatch.setenv('GOOGLE_CLIENT_ID','synthetic-client');monkeypatch.setenv('GOOGLE_CLIENT_SECRET','synthetic-secret')
 monkeypatch.setenv('CONNECTOR_ENCRYPTION_KEY',Fernet.generate_key().decode())
 return factory

def client():return TestClient(main.app,headers={'Origin':security.APP_ORIGIN})
def account(c,email):
 r=c.post('/auth/register',json={'email':email,'password':PASSWORD});assert r.status_code==200,r.text
 c.headers['X-CSRF-Token']=r.json()['csrf_token'];return r.json()

def test_auth_cookie_csrf_and_logout(env,caplog):
 c=client()
 for url in ['/events','/jobs','/metrics','/export','/evaluation','/connectors/gmail/status']:
  assert c.get(url).status_code==401
 info=account(c,'Alice@example.invalid');assert info['user']['email']=='alice@example.invalid'
 token=c.cookies.get(security.COOKIE)
 with env() as s:
  user=s.scalar(select(User));assert user.password_hash.startswith('$argon2id$')
  stored=str([u.__dict__ for u in s.scalars(select(User))])+str([u.__dict__ for u in s.scalars(select(AuthSession))])
 assert token not in stored+json.dumps(info)+caplog.text and PASSWORD not in stored+json.dumps(info)+caplog.text
 assert c.get('/auth/me').headers['cache-control']=='no-store'
 assert c.delete('/data',headers={'X-CSRF-Token':'wrong'}).status_code==403
 assert c.post('/auth/logout',headers={'X-CSRF-Token':'wrong'}).status_code==403
 assert c.get('/events',headers={'Origin':'https://attacker.invalid'}).status_code==403
 assert c.post('/auth/logout').status_code==200
 assert c.get('/events').status_code==401
 stale=client();stale.cookies.set(security.COOKIE,token);assert stale.get('/events').status_code==401
 assert c.get('/auth/me').json()['authenticated'] is False
 r=c.post('/auth/login',json={'email':'alice@example.invalid','password':PASSWORD})
 assert r.status_code==200 and c.cookies.get(security.COOKIE)!=token
 cookie=r.headers['set-cookie'].lower();assert 'httponly' in cookie and 'samesite=lax' in cookie


def test_two_accounts_cannot_access_export_correct_link_or_delete_each_other(env):
 alice,bob=client(),client();a=account(alice,'a@example.invalid');account(bob,'b@example.invalid')
 payload={'messages':[{'body':'Paid INR 100 at Cafe on 2026-10-01 txn ref PRIVATE-A'},{'body':'Purchase INR 100 at Cafe on 2026-10-01 txn ref PRIVATE-A','source':'email'}]}
 assert alice.post('/imports',json=payload).status_code==200
 record=alice.get('/events').json()[0];eid=record['id'];link=record['relationships'][0]['id']
 assert bob.get('/events',headers={'X-Owner':a['user']['id']}).json()==[]
 assert bob.get('/export').json()==[] and bob.get('/jobs').json()==[] and bob.get('/metrics').json()['records']==0
 assert bob.patch('/events/'+eid,json={'field':'merchant','value':'Stolen','reason':'test'}).status_code==404
 assert bob.patch('/relationships/'+link,json={'status':'undone'}).status_code==404
 assert bob.post('/relationships',json={'left_id':eid,'right_id':eid,'kind':'duplicate'}).status_code==404
 assert bob.post('/imports',json={**payload,'owner':a['user']['id']}).status_code==422
 assert bob.delete('/data').status_code==200
 assert len(alice.get('/events').json())==1
 assert len(alice.get('/events').json()[0]['sources'])==2


def test_idle_expiry_disabled_user_and_session_rotation(env):
 c=client();account(c,'expire@example.invalid');first=c.cookies.get(security.COOKIE)
 with env() as s:
  session=s.get(AuthSession,security.digest(first));session.last_seen_at=int(time.time())-security.IDLE_SECONDS-1;s.commit()
 assert c.get('/events').status_code==401
 assert c.post('/auth/login',json={'email':'expire@example.invalid','password':PASSWORD}).status_code==200
 second=c.cookies.get(security.COOKIE)
 with env() as s:
  assert s.get(AuthSession,security.digest(first)) is None
  user=s.scalar(select(User));user.active=False;s.commit()
 assert c.get('/events').status_code==401
 assert c.post('/auth/login',json={'email':'expire@example.invalid','password':PASSWORD}).status_code==401


def test_login_throttling_generic_errors_and_origin(env):
 c=client();account(c,'rate@example.invalid');c.post('/auth/logout')
 missing=c.post('/auth/login',json={'email':'unknown@example.invalid','password':PASSWORD})
 known=c.post('/auth/login',json={'email':'rate@example.invalid','password':'Wrong synthetic password'})
 assert missing.status_code==known.status_code==401 and missing.json()==known.json()
 for _ in range(4):assert c.post('/auth/login',json={'email':'rate@example.invalid','password':'Wrong synthetic password'}).status_code==401
 limited=c.post('/auth/login',json={'email':'rate@example.invalid','password':'Wrong synthetic password'})
 assert limited.status_code==429 and int(limited.headers['retry-after'])>0
 assert TestClient(main.app).post('/auth/login',json={'email':'rate@example.invalid','password':PASSWORD}).status_code==403
 assert c.post('/auth/register',json={'email':'other@example.invalid','password':PASSWORD,'workspace_id':'local-demo'}).status_code==422


def mock_provider(monkeypatch,messages=None):
 calls=[]
 messages=messages or {'purchase':'Paid INR 420 at Cafe on 2026-10-01','otp':'OTP 728194 for payment INR 420','private':'Family secret sentinel-private'}
 def provider(method,url,**kwargs):
  calls.append((method,url,kwargs))
  if url==gmail.TOKEN_URL:return {'access_token':'synthetic-access','refresh_token':'synthetic-refresh','token_type':'Bearer','expires_in':3600,'scope':gmail.SCOPE}
  if url==gmail.API_URL+'/profile':return {'emailAddress':'mailbox@example.invalid'}
  if url==gmail.API_URL+'/messages':return {'messages':[{'id':i} for i in messages]}
  if '/messages/' in url:
   body=messages[url.rsplit('/',1)[1]]
   return {'internalDate':'1790830800000','payload':{'mimeType':'text/plain','body':{'data':base64.urlsafe_b64encode(body.encode()).decode().rstrip('=')}}}
  if url==gmail.REVOKE_URL:return {}
  raise AssertionError('Unexpected provider URL')
 monkeypatch.setattr(gmail,'google',provider);return calls

def connect(c):
 response=c.post('/connectors/gmail/connect');assert response.status_code==200,response.text
 query=parse_qs(urlparse(response.json()['url']).query)
 assert query['scope']==[gmail.SCOPE] and query['code_challenge_method']==['S256']
 state=query['state'][0]
 callback=c.get('/connectors/gmail/callback',params={'state':state,'code':'synthetic-code'},follow_redirects=False)
 assert callback.status_code==303 and callback.headers['location'].endswith('?gmail=connected'),callback.text
 return state

def test_gmail_oauth_encryption_import_replay_privacy_and_disconnect(env,monkeypatch):
 c=client();info=account(c,'gmail@example.invalid');calls=mock_provider(monkeypatch)
 state=connect(c)
 assert c.get('/connectors/gmail/callback',params={'state':state,'code':'replay'}).status_code==400
 with env() as s:
  conn=s.get(GmailConnection,info['user']['id']);assert 'synthetic-access' not in conn.tokens_encrypted and 'synthetic-refresh' not in conn.tokens_encrypted
  assert s.scalar(select(OAuthState)) is None
 params={'after':'2026-10-01','before':'2026-10-15','limit':20,'consent':True}
 assert c.post('/connectors/gmail/import',json={**params,'consent':False}).status_code==422
 assert c.post('/connectors/gmail/import',json={**params,'before':'2026-12-01'}).status_code==422
 r=c.post('/connectors/gmail/import',json=params);assert r.status_code==200,r.text
 assert r.json()['counts']['retained']==1 and r.json()['counts']['otp']==1 and r.json()['counts']['irrelevant']==1
 assert c.post('/connectors/gmail/import',json=params).json()['counts']['reimported']==1
 with env() as s:
  snapshot=str([m.__dict__ for m in s.scalars(select(Message))])+str([j.__dict__ for j in s.scalars(select(Job))])
 assert '728194' not in snapshot+c.get('/export').text and 'sentinel-private' not in snapshot+c.get('/export').text
 assert c.get('/events').json()[0]['mode']=='rules'
 r=c.delete('/connectors/gmail/connection');assert r.json()=={'connected':False,'provider_revoked':True}
 assert not c.get('/connectors/gmail/status').json()['connected'] and len(c.get('/events').json())==1
 assert calls[-1][1]==gmail.REVOKE_URL
 assert c.post('/connectors/gmail/import',json=params).status_code==409


def test_oauth_wrong_user_wrong_session_expired_and_denied_scope(env,monkeypatch):
 a,b=client(),client();account(a,'oauth-a@example.invalid');account(b,'oauth-b@example.invalid');calls=mock_provider(monkeypatch)
 state=parse_qs(urlparse(a.post('/connectors/gmail/connect').json()['url']).query)['state'][0]
 assert b.get('/connectors/gmail/callback',params={'state':state,'code':'bad'}).status_code==400 and calls==[]
 logged=a.post('/auth/login',json={'email':'oauth-a@example.invalid','password':PASSWORD});a.headers['X-CSRF-Token']=logged.json()['csrf_token']
 assert a.get('/connectors/gmail/callback',params={'state':state,'code':'bad'}).status_code==400 and calls==[]
 state=parse_qs(urlparse(a.post('/connectors/gmail/connect').json()['url']).query)['state'][0]
 with env() as s:
  st=s.get(OAuthState,security.digest(state));st.expires_at=int(time.time())-1;s.commit()
 assert a.get('/connectors/gmail/callback',params={'state':state,'code':'bad'}).status_code==400
 state=parse_qs(urlparse(a.post('/connectors/gmail/connect').json()['url']).query)['state'][0]
 monkeypatch.setattr(gmail,'google',lambda *a,**k:{'access_token':'secret-not-retained','token_type':'Bearer','expires_in':3600,'scope':'wrong-scope'})
 response=a.get('/connectors/gmail/callback',params={'state':state,'code':'valid'},follow_redirects=False)
 assert response.headers['location'].endswith('?gmail=error') and 'secret-not-retained' not in response.text
 with env() as s:assert s.scalar(select(GmailConnection)) is None


def test_gmail_refresh_lock_disconnect_during_fetch_and_failure(env,monkeypatch):
 c=client();info=account(c,'refresh@example.invalid');calls=mock_provider(monkeypatch,{'single':'Paid INR 10 at Cafe on 2026-10-01'});connect(c)
 params={'after':'2026-10-01','before':'2026-10-15','consent':True}
 with env() as s:
  conn=s.get(GmailConnection,info['user']['id']);conn.expires_at=int(time.time())-1;conn.locked_until=int(time.time())+50;s.commit()
 assert c.post('/connectors/gmail/import',json=params).status_code==409
 with env() as s:conn=s.get(GmailConnection,info['user']['id']);conn.locked_until=0;s.commit()
 assert c.post('/connectors/gmail/import',json=params).status_code==200
 assert any(call[2].get('data',{}).get('grant_type')=='refresh_token' for call in calls)
 # Disconnect after fetch starts: no newly fetched records may be retained.
 c.delete('/data')
 original=gmail.google
 def disappearing(method,url,**kwargs):
  if '/messages/' in url:
   with env() as s:s.execute(delete(GmailConnection).where(GmailConnection.owner==info['user']['id']));s.commit()
  return original(method,url,**kwargs)
 monkeypatch.setattr(gmail,'google',disappearing)
 assert c.post('/connectors/gmail/import',json=params).status_code==409
 assert c.get('/events').json()==[] and c.get('/jobs').json()==[]


def test_connector_unconfigured_html_attachment_and_bounded_http(env,monkeypatch):
 c=client();account(c,'config@example.invalid');monkeypatch.delenv('GOOGLE_CLIENT_SECRET')
 assert c.get('/connectors/gmail/status').json()['configured'] is False
 assert c.post('/connectors/gmail/connect').status_code==503
 assert gmail.plain_body({'mimeType':'text/html','body':{'data':'private'}})==''
 assert gmail.plain_body({'mimeType':'text/plain','filename':'attachment.txt','body':{'data':'private'}})==''
 encoded=base64.urlsafe_b64encode(b'Paid INR 10 at Cafe').decode()
 assert gmail.plain_body({'mimeType':'multipart/mixed','parts':[{'mimeType':'multipart/alternative','parts':[{'mimeType':'text/plain','body':{'data':encoded}}]}]})=='Paid INR 10 at Cafe'
 factory=httpx.Client
 transport=httpx.MockTransport(lambda r:httpx.Response(200,content=b'x'*(gmail.MAX_RESPONSE+1)))
 monkeypatch.setattr(gmail.httpx,'Client',lambda **k:factory(transport=transport,**k))
 with pytest.raises(ValueError):gmail.google('GET',gmail.API_URL+'/messages')


@pytest.mark.parametrize('values',[{'AUTH_MODE':'demo'},{'ENABLE_REGISTRATION':'true'},{'LOCAL_WEB_ORIGIN':'http://127.0.0.1:3017'},{'DATABASE_URL':'sqlite://'},{'ALLOWED_HOSTS':'*'}])
def test_production_rejects_insecure_configuration(values):
 settings={**os.environ,'ENVIRONMENT':'production','AUTH_MODE':'authenticated','ENABLE_REGISTRATION':'false','LOCAL_WEB_ORIGIN':'https://proofpay.example.invalid','DATABASE_URL':'postgresql+psycopg://demo:demo@127.0.0.1:5999/demo','ALLOWED_HOSTS':'proofpay.example.invalid',**values,'PYTHONPATH':'services/api'}
 result=subprocess.run([os.path.abspath('.venv/bin/python'),'-c','from app import security'],env=settings,capture_output=True)
 assert result.returncode!=0

def test_gmail_pagination_is_account_generation_and_date_bound(env,monkeypatch):
 c=client();account(c,'pages@example.invalid');mock_provider(monkeypatch,{'single':'Paid INR 10 at Cafe on 2026-10-01'});connect(c)
 original=gmail.google;queries=[]
 def paged(method,url,**kwargs):
  result=original(method,url,**kwargs)
  if url==gmail.API_URL+'/messages':
   queries.append(kwargs['params'])
   if not kwargs['params'].get('pageToken'):result['nextPageToken']='synthetic-next-page'
  return result
 monkeypatch.setattr(gmail,'google',paged)
 payload={'after':'2026-10-01','before':'2026-10-15','consent':True}
 first=c.post('/connectors/gmail/import',json=payload);assert first.status_code==200
 cursor=first.json()['next_cursor'];assert cursor and 'synthetic-next-page' not in cursor
 assert 'after:1790792999 before:1792002600' in queries[0]['q']
 wrong=c.post('/connectors/gmail/import',json={**payload,'after':'2026-10-02','cursor':cursor});assert wrong.status_code==400
 next_page=c.post('/connectors/gmail/import',json={**payload,'cursor':cursor});assert next_page.status_code==200
 assert queries[-1]['pageToken']=='synthetic-next-page' and next_page.json()['counts']['reimported']==1
 assert next_page.json()['next_cursor'] is None


def test_secure_cookie_registration_disable_and_missing_csrf(env,monkeypatch):
 c=client();account(c,'secure@example.invalid')
 assert c.post('/imports',json={'messages':[{'body':'Paid INR 2 at Cafe'}]},headers={'X-CSRF-Token':''}).status_code==403
 monkeypatch.setattr(security,'REGISTRATION_ENABLED',False)
 assert c.post('/auth/register',json={'email':'closed@example.invalid','password':PASSWORD}).status_code==403
 monkeypatch.setattr(security,'ENVIRONMENT','production')
 response=c.post('/auth/login',json={'email':'secure@example.invalid','password':PASSWORD})
 assert 'Secure' in response.headers['set-cookie']


def test_operator_adopts_demo_without_changing_record_identity_or_replay(env,monkeypatch):
 import importlib.util
 from app.service import import_batch,projection
 from app.schema import InputMessage
 c=client();info=account(c,'operator@example.invalid')
 body='Paid INR 88 at Cafe on 2026-10-01 txn ref LEGACY'
 monkeypatch.setenv('LOCAL_OWNER','legacy-test')
 with env() as s:
  import_batch(s,[InputMessage(body=body)],'legacy-test')
  before=projection(s,'legacy-test')[0]['id']
 assert c.get('/events').json()==[]
 spec=importlib.util.spec_from_file_location('manage_users','scripts/manage_users.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 monkeypatch.setattr(module,'Session',env)
 monkeypatch.setattr('sys.argv',['manage_users','adopt-demo','--email','operator@example.invalid']);module.main()
 assert c.get('/events').status_code==401
 logged=c.post('/auth/login',json={'email':'operator@example.invalid','password':PASSWORD});c.headers['X-CSRF-Token']=logged.json()['csrf_token']
 assert c.get('/events').json()[0]['id']==before
 assert c.post('/imports',json={'messages':[{'body':body}]}).json()['counts']['reimported']==1

def test_disconnect_invalidates_pending_and_inflight_oauth(env,monkeypatch):
 c=client();info=account(c,'cancel@example.invalid');mock_provider(monkeypatch)
 state=parse_qs(urlparse(c.post('/connectors/gmail/connect').json()['url']).query)['state'][0]
 assert c.delete('/connectors/gmail/connection').status_code==200
 assert c.get('/connectors/gmail/callback',params={'state':state,'code':'cancelled'}).status_code==400
 state=parse_qs(urlparse(c.post('/connectors/gmail/connect').json()['url']).query)['state'][0]
 original=gmail.google
 def cancel_mid_exchange(method,url,**kwargs):
  if url==gmail.API_URL+'/profile':
   with env() as s:
    user=s.get(User,info['user']['id']);user.gmail_epoch+=1;s.commit()
  return original(method,url,**kwargs)
 monkeypatch.setattr(gmail,'google',cancel_mid_exchange)
 response=c.get('/connectors/gmail/callback',params={'state':state,'code':'in-flight'},follow_redirects=False)
 assert response.headers['location'].endswith('?gmail=cancelled')
 assert not c.get('/connectors/gmail/status').json()['connected']
