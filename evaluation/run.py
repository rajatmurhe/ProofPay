import argparse,json,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/api'))
from app.parser import gate,extract
from app.schema import InputMessage
from app.db import Base, Relationship, MessageEvent, Message
from app.service import import_batch,rows
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
p=argparse.ArgumentParser();p.add_argument('--split',choices=['development','test'],default='development');p.add_argument('--mode',choices=['rules','fixture'],default='rules');args=p.parse_args()
cases=[c for c in json.loads(Path(__file__).with_name('dataset.json').read_text()) if c['split']==args.split]
classes=['Transaction','Payment','Refund','OTP','Credit Card Bill','Offer/Promotion','Cashback/Reward','EMI','Failed Transaction','Other']
tp=fp=fn=0;amount_good=amount_total=valid_good=valid_total=retained=0;failures=[];truth=[];pred=[];lat=[];date_good=date_total=0
for c in cases:
 start=time.perf_counter();g=gate(c['body']);events=extract(c['body'],args.mode) if g=='relevant' else [];lat.append((time.perf_counter()-start)*1000)
 relevant=g=='relevant';expected=c['labels']['relevance'];tp+=relevant and expected;fp+=relevant and not expected;fn+=not relevant and expected;retained+=relevant
 cls='OTP' if g=='otp' else events[0].message_type if events else None
 if expected or c['labels']['message_type']=='OTP':truth.append(c['labels']['message_type']);pred.append(cls)
 actual=[[a.role,a.minor,a.currency] for e in events for a in e.amounts]
 wanted=c['labels']['amounts'];ok=actual==wanted
 if expected:amount_total+=1;amount_good+=ok
 if 'event_date' in c['labels']:
  date_total+=1;date_good+=bool(events and str(events[0].event_date)==c['labels']['event_date'])
 is_valid=bool(events) and all(e.quality=='validated' for e in events)
 if is_valid:
  valid_total+=1;valid_good+=bool(expected and ok and cls==c['labels']['message_type'] and ('status' not in c['labels'] or events[0].status==c['labels']['status']) and ('event_date' not in c['labels'] or str(events[0].event_date)==c['labels']['event_date']))
 status_ok='status' not in c['labels'] or bool(events and events[0].status==c['labels']['status'])
 date_ok='event_date' not in c['labels'] or bool(events and str(events[0].event_date)==c['labels']['event_date'])
 if relevant!=expected or (expected and (not ok or cls!=c['labels']['message_type'] or not status_ok or not date_ok)):
  failures.append({'id':c['id'],'synthetic_body':c['body'],'expected':c['labels'],'actual':{'relevance':relevant,'message_type':cls,'amounts':actual,'quality':[e.quality for e in events],'status':[e.status for e in events],'event_date':[str(e.event_date) if e.event_date else None for e in events]}})
def ratio(a,b):return round(a/b,4) if b else None
per={}
for cls in classes:
 t=sum(a==b==cls for a,b in zip(truth,pred));f=sum(a!=cls and b==cls for a,b in zip(truth,pred));n=sum(a==cls and b!=cls for a,b in zip(truth,pred));per[cls]={'support':truth.count(cls),'precision':ratio(t,t+f),'recall':ratio(t,t+n),'f1':ratio(2*t,2*t+f+n)}
# Evaluate pairwise duplicate and purchase/refund truth in a fresh database.
linked=[c for c in cases if c['labels'].get('duplicate_group')];pair_truth=set();pair_pred=set();rel_truth=set();rel_pred=set()
engine=create_engine('sqlite://');Base.metadata.create_all(engine)
with Session(engine) as s:
 mapping={}
 for c in linked:
  result=import_batch(s,[InputMessage(body=c['body'],source_id=c['id'])],'eval',args.mode)
  msg=s.scalar(select(Message).where(Message.job_id==result['id']))
  eid=s.scalar(select(MessageEvent.event_id).where(MessageEvent.message_id==msg.id));mapping[eid]=c
 for i,a in enumerate(linked):
  for b in linked[i+1:]:
   if a['labels']['duplicate_group']==b['labels']['duplicate_group']:pair_truth.add(tuple(sorted([a['id'],b['id']])))
 for a in linked:
  if a['labels'].get('refund_target'):rel_truth.add((a['labels']['refund_target'],a['labels']['duplicate_group']))
 for r in rows(s,Relationship,'eval'):
  if r.status!='accepted':continue
  a,b=mapping[r.left_id],mapping[r.right_id]
  if r.kind=='duplicate':pair_pred.add(tuple(sorted([a['id'],b['id']])))
  else:rel_pred.add((a['labels']['duplicate_group'],b['labels']['duplicate_group']))
report={'dataset':'synthetic only; no consented real data','split':args.split,'evaluation_status':'Regression benchmark after inspecting and fixing known sample failures; not an unseen-data estimate.','mode':args.mode,'count':len(cases),'families':len(set(c['family'] for c in cases)),'relevance':{'tp':tp,'fp':fp,'fn':fn,'precision':ratio(tp,tp+fp),'recall':ratio(tp,tp+fn)},'classification':{'macro_f1':round(sum(v['f1'] or 0 for v in per.values())/len(classes),4),'per_class':per},'explicit_amount_currency_role_exact_match':{'correct':amount_good,'total':amount_total,'accuracy':ratio(amount_good,amount_total)},'explicit_event_date_exact_match':{'correct':date_good,'total':date_total,'accuracy':ratio(date_good,date_total)},'auto_validated_critical_accuracy':{'correct':valid_good,'total':valid_total,'accuracy':ratio(valid_good,valid_total),'coverage_of_relevant_truth':ratio(valid_total,sum(c['labels']['relevance'] for c in cases))},'duplicates':{'predicted':len(pair_pred),'expected':len(pair_truth),'correct':len(pair_pred&pair_truth),'precision':ratio(len(pair_pred&pair_truth),len(pair_pred)),'recall':ratio(len(pair_pred&pair_truth),len(pair_truth))},'relationships':{'predicted':len(rel_pred),'expected':len(rel_truth),'correct':len(rel_pred&rel_truth),'precision':ratio(len(rel_pred&rel_truth),len(rel_pred)),'recall':ratio(len(rel_pred&rel_truth),len(rel_truth))},'latency_ms':{'mean':round(sum(lat)/len(lat),3),'max':round(max(lat),3)},'provider':{'calls':0,'tokens':None,'cost':None,'live_verified':False},'failure_examples':failures,'limitations':['Small synthetic benchmark; not statistically representative.','Critical accuracy checks labelled type, amount roles, currency, status and dates where labelled; not every possible extracted field.','No learned classifier, so no training split. Families and linked groups do not cross development/test.','Fixture mode runs deterministic rules against explicit synthetic fixtures; it does not simulate a live provider.']}
path=Path(__file__).with_name(f'report-{args.split}-{args.mode}.json');path.write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['failure_examples','classification']},indent=2))
