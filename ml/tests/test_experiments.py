import copy
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ml.train import validate_splits, fit_and_report
from ml.predict import predict
from evaluation import compare

CORPUS=Path(__file__).resolve().parents[1]/'corpus.json'

def test_group_and_exact_text_leakage_rejected():
 rows=json.loads(CORPUS.read_text());validate_splits(rows)
 leaked=copy.deepcopy(rows);leaked[-1]['family']=leaked[0]['family']
 with pytest.raises(ValueError,match='leakage'):validate_splits(leaked)
 leaked=copy.deepcopy(rows);leaked[-1]['body']=leaked[0]['body']
 with pytest.raises(ValueError,match='leakage'):validate_splits(leaked)

def test_test_labels_do_not_tune_model_or_threshold():
 rows=json.loads(CORPUS.read_text());report,artifact=fit_and_report(rows,'test')
 changed=copy.deepcopy(rows)
 for row in changed:
  if row['split']=='test':row['label']='Other'
 _,again=fit_and_report(changed,'test')
 assert artifact==again
 # JSON-only weights must be usable outside training, without pickle.
 restored=json.loads(json.dumps(artifact));result=predict('Refund INR 125 credited for your order at Aster Books.',restored)
 assert result['label']=='Refund' and 0<=result['score']<=1
 assert predict('OTP 730100 for payment INR 125',restored)['source']=='local privacy gate'
 assert predict('zxqv qqqzzz',restored)['review_required']

def test_grounding_rejects_invented_amount_currency_and_date():
 body='Paid INR 125 at Cafe on 2026-10-01'
 fields={'relevant':True,'message_type':'Transaction','amounts':[{'role':'purchase','minor':12500,'currency':'INR','evidence':'INR 125'}],'event_date':'2026-10-01'}
 assert compare.grounded(compare.Prediction.model_validate(fields),body)['amounts']==[['purchase',12500,'INR']]
 for key,value in [('minor',99900),('currency','USD'),('evidence','INR 999')]:
  altered=copy.deepcopy(fields);altered['amounts'][0][key]=value
  with pytest.raises(ValueError):compare.grounded(compare.Prediction.model_validate(altered),body)
 fields['event_date']='2026-10-02'
 with pytest.raises(ValueError):compare.grounded(compare.Prediction.model_validate(fields),body)

def test_provider_opt_in_budget_otp_gate_and_failure_reporting(monkeypatch):
 for key in ['AI_BASE_URL','AI_MODEL','AI_API_KEY']:monkeypatch.setenv(key,'synthetic')
 cases=[{'id':'otp','body':'OTP 730100 for payment INR 125','labels':{'relevance':False,'message_type':'OTP'}},{'id':'purchase','body':'Paid INR 125 at Cafe','labels':{'relevance':True,'message_type':'Transaction','amounts':[['purchase',12500,'INR']]}},{'id':'more','body':'Paid INR 499 at Cafe','labels':{'relevance':True,'message_type':'Transaction','amounts':[['purchase',49900,'INR']]}}]
 assert compare.benchmark(cases,'llm')['status']=='not_run'
 calls=[]
 def fail(body):calls.append(body);raise ValueError('secret response')
 monkeypatch.setattr(compare,'call_llm',fail)
 r=compare.benchmark(cases,'llm',True,max_calls=1)
 assert len(calls)==1 and 'OTP' not in calls[0]
 assert r['provider_attempts']==1 and r['provider_errors']==2 and r['estimated_cost_usd'] is None
 assert r['cases'][1]['prediction'] is None and r['cases'][2]['error']=='call_budget_exhausted'
 assert 'secret response' not in json.dumps(r)
