import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.db import Base, Event, Message, Relationship
from app.parser import parse,gate,extract,mask
from app.service import import_batch,projection,metrics
from app.schema import InputMessage
from app.adapters import parse_upload,ImportErrorSafe

@pytest.mark.parametrize('text,kind',[
 ('Debited INR 30 at Cafe on 2026-10-01','Transaction'),
 ('Credit card payment INR 900 received on 2026-10-01','Payment'),
 ('Refund INR 50 initiated on 2026-10-01','Refund'),
 ('Total due INR 500; minimum due INR 50; due date 2026-11-01','Credit Card Bill'),
 ('Offer INR 200 discount with your card','Offer/Promotion'),
 ('Cashback INR 25 credited on 2026-10-01','Cashback/Reward'),
 ('EMI INR 200 debited on 2026-10-01','EMI'),
 ('Payment INR 200 failed on 2026-10-01','Failed Transaction'),
 ('Account balance INR 90','Other'),
])
def test_classes(text,kind):assert parse(text).message_type==kind

def test_roles_and_dates():
 e=parse('HDFC credit card total due INR 12,840; minimum due INR 642; due date 2026-12-20')
 assert [(a.role,a.minor) for a in e.amounts]==[('total due',1284000),('minimum due',64200)]
 assert str(e.due_date)=='2026-12-20' and e.event_date is None
 e=parse('A/c XX7712 debited Rs. 1,23,499 at Amazon on 2026-10-02. Avl bal INR 90,000')
 assert e.amounts[0].minor==12349900 and e.amounts[1].role=='balance'
 assert parse('Debited INR 1,2').quality!='validated'

def test_uncertainty():
 assert parse('Paid $12 at Cafe on 2026-10-02').amounts[0].currency is None
 assert parse('Paid INR 12 via UPI').instrument_type=='unknown'
 assert parse('Paid INR 12 at Amazon Pay on 2026-10-02').merchant is None
 assert parse('Payment INR 12 failed; bank account debited').conflicts
 assert gate('OTP 123456 for INR 999')=='otp'
 assert gate('payment ka paisa bheja')=='uncertain'
 assert len(extract('Paid INR 10 at Cafe on 2026-10-02 || Paid INR 20 at Metro on 2026-10-02'))==2

def session():
 engine=create_engine('sqlite://');Base.metadata.create_all(engine);return Session(engine)
def test_no_weak_merge_and_multiple_refunds():
 with session() as s:
  msgs=[
   'Paid INR 1000 at Amazon on 2026-10-01 txn ref A111 order id ORD-A',
   'Paid INR 1000 at Amazon on 2026-10-01 txn ref A222 order id ORD-B',
   'Refund INR 100 credited at Amazon on 2026-10-02 refund ref R111 order id ORD-A',
   'Refund INR 200 credited at Amazon on 2026-10-03 refund ref R222 order id ORD-A',
   'Credit card payment INR 1000 received on 2026-10-03 txn ref PAY123',
  ]
  import_batch(s,[InputMessage(body=m) for m in msgs],'a')
  events=projection(s,'a');assert len(events)==5
  assert next(e for e in events if e.get('order_ref')=='ORD-A' and e['subtype']=='purchase')['net_minor']==70000
  assert metrics(events)['currencies']['INR']['purchase']==200000
  link=s.scalar(select(Relationship).where(Relationship.kind=='refund'));link.status='undone';s.commit()
  assert next(e for e in projection(s,'a') if e.get('order_ref')=='ORD-A' and e['subtype']=='purchase')['net_minor'] in [80000,90000]

def test_conflicting_reference_and_privacy(caplog):
 with session() as s:
  msgs=['Paid INR 100 at Cafe on 2026-10-01 txn ref SAME','Paid INR 200 at Cafe on 2026-10-01 txn ref SAME','OTP 654321 for INR 200','Private family secret at 9pm']
  import_batch(s,[InputMessage(body=m) for m in msgs],'a')
  assert len(projection(s,'a'))==2
  assert all(e['quality']=='needs review' for e in projection(s,'a'))
  stored=str([m.__dict__ for m in s.scalars(select(Message))])
  assert '654321' not in stored and 'family secret' not in stored and '654321' not in caplog.text

def test_adapter_validation():
 for name,data in [('x.json',b'<html>no</html>'),('x.csv',b'foo\nbar'),('x.eml',b'garbage'),('x.exe',b'hi'),('x.json',b' '*2097153)]:
  with pytest.raises(ImportErrorSafe):parse_upload(name,data)

def test_provider_otp_and_missing_credentials(monkeypatch):
 from app.provider import augment
 monkeypatch.delenv('AI_API_KEY',raising=False)
 assert augment('OTP 123456 for INR 100',[] )==([],False)
 assert augment('Account balance INR 100',[] )==([],True)

def test_refund_with_reused_order_does_not_reduce_two_purchases():
 with session() as s:
  texts=['Paid INR 1000 at Amazon on 2026-10-01 txn ref ONE order id REUSED','Paid INR 1000 at Amazon on 2026-10-01 txn ref TWO order id REUSED','Refund INR 100 credited at Amazon on 2026-10-02 refund ref REF order id REUSED']
  import_batch(s,[InputMessage(body=t) for t in texts],'a')
  assert sum(e['net_minor'] for e in projection(s,'a') if e['subtype']=='purchase')==200000
  assert all(r.status=='suggested' for r in s.scalars(select(Relationship).where(Relationship.kind=='refund')))

def test_offer_threshold_never_counts_as_purchase_spending():
 with session() as s:
  import_batch(s,[InputMessage(body='Offer: spend INR 2000 and get discount INR 200 with card')],'a')
  events=projection(s,'a')
  assert len(events)==1 and events[0]['message_type']=='Offer/Promotion'
  assert metrics(events)['currencies']=={}

@pytest.mark.parametrize('text,kind,amounts',[
 ('Card statement: total due INR 2400. minimum due INR 120. due by 2026-12-04','Credit Card Bill',[('total due',240000),('minimum due',12000)]),
 ('UPI payment of INR 82.50 declined on 2026-10-05.','Failed Transaction',[('unknown',8250)]),
 ('Transaction INR 320 unsuccessful on 2026-10-06','Failed Transaction',[('unknown',32000)]),
 ('Aapke a/c se INR 230 debit hua','Transaction',[('purchase',23000)]),
 ('Paid INR 14.25 at Cafe on 2026-10-05.','Transaction',[('purchase',1425)]),
])
def test_financial_wording_and_sentence_punctuation(text,kind,amounts):
 assert gate(text)=='relevant'
 events=extract(text);assert len(events)==1
 assert events[0].message_type==kind
 assert [(a.role,a.minor) for a in events[0].amounts]==amounts
 if kind=='Credit Card Bill':assert str(events[0].due_date)=='2026-12-04'
 if 'debit hua' in text:assert events[0].quality=='needs review'

def test_malformed_decimal_is_not_partially_accepted():
 assert parse('Paid INR 14.259 at Cafe on 2026-10-05').amounts==[]
 assert gate('OTP 765432: your payment of INR 82 declined')=='otp'
 assert gate('My dinner invitation was declined. Bring INR 100.')!='relevant'
