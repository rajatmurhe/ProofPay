import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.db import Base,Event,Message,Job,Relationship,Audit
from app import main
from app.schema import InputMessage
from app.service import import_batch,projection

@pytest.fixture
def env(monkeypatch):
 engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(engine)
 factory=sessionmaker(engine,expire_on_commit=False);monkeypatch.setattr(main,'Session',factory)
 return TestClient(main.app),factory

def test_scope_and_deletion(env,monkeypatch):
 client,factory=env
 with factory() as s:
  import_batch(s,[InputMessage(body='Paid INR 70 at Cafe on 2026-10-01')],'other-owner')
  foreign=projection(s,'other-owner')[0]['id']
 assert client.get('/events').json()==[]
 assert client.patch('/events/'+foreign,json={'field':'merchant','value':'Wrong','reason':'test'}).status_code==404
 assert client.post('/relationships',json={'left_id':foreign,'right_id':foreign,'kind':'duplicate'}).status_code==404
 client.post('/imports',json={'messages':[{'body':'Paid INR 90 at Cafe on 2026-10-01'}]})
 assert len(client.get('/events').json())==1
 assert client.delete('/data').json()['deleted']
 assert client.get('/events').json()==[] and client.get('/jobs').json()==[]
 with factory() as s:assert len(projection(s,'other-owner'))==1

def test_no_sensitive_content_in_db_response_logs(env,caplog):
 client,factory=env
 payload={'messages':[{'body':'OTP 914827 for INR 999'},{'body':'Private diagnosis sentinel-SECRET-55'},{'body':'Payment check sentinel-UNCERTAIN-23'}]}
 result=client.post('/imports',json=payload);assert result.status_code==200
 with factory() as s:
  assert list(s.scalars(select(Message)))==[] and list(s.scalars(select(Event)))==[]
  stored=json.dumps([j.counts for j in s.scalars(select(Job))])
 for token in ['914827','sentinel-SECRET-55','sentinel-UNCERTAIN-23']:
  assert token not in stored+result.text+caplog.text
 invalid=client.post('/imports',json={'messages':[{'body':'private-sentinel','unknown':'hidden'}]})
 assert invalid.status_code==422 and 'private-sentinel' not in invalid.text

def test_malformed_and_oversize_uploads(env):
 client,_=env
 for filename,body in [('x.json',b'{secret malformed'),('x.json',b'\x00bad'),('x.eml',b'From: a@example.invalid\nDate: Fri, 02 Oct 2026 10:00:00 +0530\nContent-Type: text/html\n\n<img src="https://example.invalid/tracker">'),('x.csv',b'private\nsecret'),('x.json',b'a'*2097153)]:
  response=client.post('/imports/files',files={'files':(filename,body)})
  assert response.status_code==400 and 'secret' not in response.text
 response=client.post('/imports/files',files=[('files',(f'{i}.json',b'[]')) for i in range(6)])
 assert response.status_code==400
 assert client.post('/imports',json={'messages':[{'body':'hello'}]},headers={'origin':'https://attacker.invalid'}).status_code==403

def test_correction_csv_and_undo(env):
 client,_=env
 msgs=[{'body':'Paid INR 80 at Cafe on 2026-10-01 txn ref MERGE'},{'body':'Purchase INR 80 at Cafe on 2026-10-01 txn ref MERGE','source':'email'}]
 client.post('/imports',json={'messages':msgs})
 e=client.get('/events').json()[0];assert len(e['sources'])==2
 assert client.patch('/events/'+e['id'],json={'field':'merchant','value':'=HYPERLINK(unsafe)','reason':'test'}).status_code==200
 assert "'=HYPERLINK" in client.get('/export?format=csv').text
 link=e['relationships'][0]['id'];assert client.patch('/relationships/'+link,json={'status':'undone'}).status_code==200
 assert len(client.get('/events').json())==2

def test_partial_batch_retry(env,monkeypatch):
 client,_=env
 from app import service
 original=service.extract
 def flaky(text,mode):
  if 'BROKEN' in text:raise ValueError('DO_NOT_LOG')
  return original(text,mode)
 monkeypatch.setattr(service,'extract',flaky)
 batch={'messages':[{'body':'Paid INR 20 at Cafe on 2026-10-01'},{'body':'Paid INR 30 at BROKEN on 2026-10-01'}]}
 r=client.post('/imports',json=batch).json();assert r['status']=='partial' and r['counts']['retained']==1 and r['counts']['failed']==1
 r=client.post('/imports',json=batch).json();assert r['counts']['reimported']==1

def test_provider_invalid_output_and_timeout(monkeypatch):
 from app import provider
 from app.parser import parse
 import httpx
 for k,v in [('AI_BASE_URL','https://provider.example.invalid/v1'),('AI_MODEL','configured-model'),('AI_API_KEY','test-only')]:monkeypatch.setenv(k,v)
 class Fake:
  def __init__(self,*a,**kw):pass
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def post(self,*a,**kw):raise httpx.TimeoutException('private source hidden')
 monkeypatch.setattr(provider.httpx,'Client',Fake)
 fallback=[parse('Account balance INR 100')]
 assert provider.augment('Account balance INR 100',fallback)==(fallback,True)
 class Response:
  content=b'{}'
  def raise_for_status(self):pass
  def json(self):return {'choices':[{'message':{'content':'{"amounts":[{"role":"purchase","minor":99999,"currency":"INR","evidence":"INR 999.99"}]}'}}]}
 Fake.post=lambda *args,**kwargs:Response()
 assert provider.augment('Account balance INR 100',fallback)==(fallback,True)

def test_valid_json_csv_and_eml_adapters():
 from app.adapters import parse_upload
 import csv,io
 for name,data in [
  ('messages.json',b'[{"body":"Paid INR 42 at Cafe on 2026-10-01","source":"sms"}]'),
  ('messages.csv',b'body,source,source_id\n"Paid INR 42 at Cafe on 2026-10-01",sms,csv-1\n'),
  ('mail.eml',b'From: statement@example.invalid\nDate: Fri, 02 Oct 2026 10:00:00 +0530\nMessage-ID: <x@example.invalid>\nContent-Type: text/plain; charset=utf-8\n\nPaid INR 42 at Cafe on 2026-10-01\n> Quoted private reply should be excluded\n'),
 ]:
  result=parse_upload(name,data);assert len(result)==1 and 'Paid INR 42' in result[0].body and 'Quoted private' not in result[0].body
