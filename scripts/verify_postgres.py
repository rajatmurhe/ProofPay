"""Run against a migrated PostgreSQL DB; isolates and deletes only its own synthetic owner."""
import sys,uuid,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/api'))
from app.db import Session,engine,Job,Message,Event,MessageEvent,Relationship,Audit
from app.service import import_batch,projection,rows
from app.schema import Batch
from sqlalchemy import delete
assert engine.dialect.name=='postgresql','Set DATABASE_URL to the migrated PostgreSQL instance'
owner='verification-'+str(uuid.uuid4())
data=json.loads((Path(__file__).resolve().parents[1]/'data/synthetic/demo.json').read_text())
with Session() as s:
 try:
  first=import_batch(s,Batch(messages=data[:6]).messages,owner)
  assert first['counts']['retained']==4,first
  events=projection(s,owner);purchase=next(e for e in events if e['subtype']=='purchase')
  assert purchase['net_minor']==100000 and len(purchase['sources'])==2
  second=import_batch(s,Batch(messages=data[:6]).messages,owner)
  assert second['counts']['reimported']==4
  print('PostgreSQL migration, golden journey, evidence, replay: PASS')
 finally:
  ids=[e.id for e in rows(s,Event,owner)]
  s.execute(delete(MessageEvent).where(MessageEvent.event_id.in_(ids)))
  for model in [Audit,Relationship,Event,Message,Job]:s.execute(delete(model).where(model.owner==owner))
  s.commit()
