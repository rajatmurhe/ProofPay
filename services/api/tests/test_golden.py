import json
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.db import Base, Message, Event
from app.schema import Batch, InputMessage
from app.service import import_batch, projection, metrics

def test_golden():
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    data=json.loads((Path(__file__).resolve().parents[3]/'data/synthetic/demo.json').read_text())
    with Session(engine) as s:
        import_batch(s,Batch(messages=data[:3]).messages,'a')
        p=next(e for e in projection(s,'a') if e['subtype']=='purchase')
        assert len(p['sources'])==2 and p['net_minor']==149900 and p['pending_refund_minor']==49900
        import_batch(s,Batch(messages=data[3:4]).messages,'a')
        p=next(e for e in projection(s,'a') if e['subtype']=='purchase')
        assert p['net_minor']==100000 and p['pending_refund_minor']==0 and p['received_refund_minor']==49900
        result=import_batch(s,Batch(messages=data[:6]).messages,'a')
        assert result['counts']['reimported']==4 and result['counts']['otp']==1 and result['counts']['irrelevant']==1
        assert len(list(s.scalars(select(Message))))==4
        assert metrics(projection(s,'a'))['currencies']['INR']['purchase']==149900
        assert projection(s,'b')==[]
