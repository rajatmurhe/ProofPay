"""Local experimental classifier. Reads one message from stdin; never saves its text."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/api'))
from app.parser import gate


def predict(body,artifact):
 if gate(body)=='otp':return {'label':'OTP','review_required':True,'source':'local privacy gate','experimental':True}
 settings=artifact['settings']
 vector=TfidfVectorizer(vocabulary=artifact['vocabulary'],ngram_range=tuple(settings['ngram_range']),sublinear_tf=settings['sublinear_tf'],norm=settings['norm'],token_pattern=settings['token_pattern'])
 vector.idf_=np.array(artifact['idf'])
 features=vector.transform([body])
 logits=np.asarray(features @ np.array(artifact['coefficients']).T)+np.array(artifact['intercepts'])
 weights=np.exp(logits-logits.max());scores=weights/weights.sum();best=int(scores.argmax());score=float(scores[0,best])
 return {'label':artifact['classes'][best],'score':score,'review_required':features.nnz==0 or score<artifact['review_threshold'],'experimental':True,'note':'Uncalibrated model score. Classification only; no financial facts are saved.'}

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--model',type=Path,default=Path(__file__).with_name('reports')/'classifier-model.json');args=parser.parse_args()
 if not args.model.exists():parser.error('Run ml/train.py first to generate local weights.')
 body=sys.stdin.read(20001)
 if len(body)>20000:parser.error('Message exceeds the 20,000 character limit.')
 print(json.dumps(predict(body,json.loads(args.model.read_text())),indent=2))
