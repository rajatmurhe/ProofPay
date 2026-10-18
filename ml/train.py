"""Reproducible TF-IDF + logistic regression experiment, never used to auto-post facts."""
import argparse
import hashlib
import json
import time
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix, f1_score
import sklearn
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"services/api"))
from app.parser import gate, extract


def validate_splits(rows):
 ids=set();groups={};bodies={}
 for row in rows:
  if row['split'] not in {'train','validation','test'}:raise ValueError('Unknown split')
  if row['id'] in ids:raise ValueError('Duplicate ID')
  ids.add(row['id'])
  for key,table in [(row['family'],groups),(' '.join(row['body'].lower().split()),bodies)]:
   if key in table and table[key]!=row['split']:raise ValueError('Cross-split leakage')
   table[key]=row['split']
 for split in ['train','validation','test']:
  if not any(r['split']==split for r in rows):raise ValueError('Missing split')
 train_classes={r['label'] for r in rows if r['split']=='train'}
 if any(r['label'] not in train_classes for r in rows):raise ValueError('Unseen training class')


def fit_and_report(rows, corpus_hash):
 validate_splits(rows)
 subsets={k:[r for r in rows if r['split']==k] for k in ['train','validation','test']}
 train,val,test=[subsets[k] for k in ['train','validation','test']]
 model=Pipeline([('tfidf',TfidfVectorizer(ngram_range=(1,2),sublinear_tf=True,max_features=20000)),('classifier',LogisticRegression(C=1.0,class_weight='balanced',max_iter=1000,random_state=42))])
 model.fit([r['body'] for r in train],[r['label'] for r in train])
 # Choose a review threshold using validation only. These scores are not calibrated confidence.
 probs=model.predict_proba([r['body'] for r in val]);scores=probs.max(axis=1);pred=model.classes_[probs.argmax(axis=1)]
 candidates=[]
 for threshold in [0,.2,.3,.4,.5,.6,.7,.8,.9,1.0]:
  accepted=scores>=threshold
  accuracy=float(np.mean(pred[accepted]==np.array([r['label'] for r in val])[accepted])) if accepted.any() else None
  candidates.append({'threshold':threshold,'coverage':float(accepted.mean()),'accuracy':accuracy})
 eligible=[x for x in candidates if x['accuracy'] is not None and x['accuracy']>=.9]
 chosen=max(eligible,key=lambda x:x['coverage']) if eligible else candidates[-1]
 start=time.perf_counter();prob=model.predict_proba([r['body'] for r in test]);elapsed=time.perf_counter()-start
 guessed=model.classes_[prob.argmax(axis=1)];truth=[r['label'] for r in test];accepted=prob.max(axis=1)>=chosen['threshold']
 classes=list(model.classes_)
 report={'corpus_sha256':corpus_hash,'seed':42,'sklearn_version':sklearn.__version__,'model':'word TF-IDF (1,2) + balanced logistic regression, C=1','data':'synthetic template-family split; not real-world accuracy','split_counts':{k:len(v) for k,v in subsets.items()},'family_counts':{k:len({r['family'] for r in v}) for k,v in subsets.items()},'validation_threshold_search':candidates,'selected_threshold':chosen['threshold'],'test':{'macro_f1':float(f1_score(truth,guessed,average='macro',zero_division=0)),'per_class':classification_report(truth,guessed,output_dict=True,zero_division=0),'confusion_matrix':{'labels':classes,'rows_truth_columns_prediction':confusion_matrix(truth,guessed,labels=classes).tolist()},'review_rate':float(1-accepted.mean()),'accepted_accuracy':float(np.mean(guessed[accepted]==np.array(truth)[accepted])) if accepted.any() else None,'inference_ms_per_message':1000*elapsed/len(test),'errors':[{'id':r['id'],'expected':r['label'],'predicted':str(g),'score':float(v.max())} for r,g,v in zip(test,guessed,prob) if r['label']!=g]},'limitations':['Agent-authored synthetic templates share vocabulary and cannot establish real-mail performance.','Validation and test each have only one template per class.','After report inspection, this corpus is a development benchmark; reserve independently collected data for a future final evaluation.','Review threshold targets 90% validation accuracy, not a production accuracy guarantee.','Model is experimental and does not bypass the OTP/privacy gate or update financial facts.']}
 # Evaluate rules on the same labels and split; never compare across different corpora.
 baseline=[]
 for row in test:
  relevance=gate(row['body']);events=extract(row['body'],'rules') if relevance=='relevant' else []
  baseline.append('OTP' if relevance=='otp' else events[0].message_type if events else 'Other')
 report['rules_baseline_on_same_test']={'macro_f1':float(f1_score(truth,baseline,average='macro',zero_division=0)),'per_class':classification_report(truth,baseline,output_dict=True,zero_division=0),'mapping':'OTP gate maps to OTP; messages without extracted events map to Other.'}
 # Human-inspectable weights and vocabulary instead of executable pickle.
 vector=model.named_steps['tfidf'];clf=model.named_steps['classifier']
 artifact={'schema_version':1,'corpus_sha256':corpus_hash,'classes':classes,'vocabulary':{k:int(v) for k,v in vector.vocabulary_.items()},'idf':vector.idf_.tolist(),'coefficients':clf.coef_.tolist(),'intercepts':clf.intercept_.tolist(),'review_threshold':chosen['threshold'],'settings':{'ngram_range':[1,2],'sublinear_tf':True,'norm':'l2','token_pattern':vector.token_pattern}}
 return report,artifact

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--corpus',type=Path,default=Path(__file__).with_name('corpus.json'));parser.add_argument('--output',type=Path,default=Path(__file__).with_name('reports'));args=parser.parse_args()
 raw=args.corpus.read_bytes();report,artifact=fit_and_report(json.loads(raw),hashlib.sha256(raw).hexdigest())
 args.output.mkdir(parents=True,exist_ok=True)
 (args.output/'classifier-report.json').write_text(json.dumps(report,indent=2)+'\n')
 (args.output/'classifier-model.json').write_text(json.dumps(artifact,indent=2)+'\n')
 print(json.dumps({'macro_f1':report['test']['macro_f1'],'review_rate':report['test']['review_rate'],'report':str(args.output/'classifier-report.json')}))
