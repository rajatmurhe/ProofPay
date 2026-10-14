import {ArrowRight, CheckCheck, AlertCircle} from 'lucide-react';
import type {Job} from '../lib/domain';

type Accuracy={correct:number;total:number;accuracy:number|null};
type LinkScore={correct:number;expected:number;predicted:number;precision:number|null;recall:number|null};
export type EvaluationReport={
 count:number;
 relevance:{tp:number;fp:number;fn:number;precision:number|null;recall:number|null};
 classification:{macro_f1:number};
 explicit_amount_currency_role_exact_match:Accuracy;
 explicit_event_date_exact_match:Accuracy;
 auto_validated_critical_accuracy:Accuracy&{coverage_of_relevant_truth:number|null};
 duplicates:LinkScore;
 relationships:LinkScore;
 provider:{live_verified:boolean};
};

function fraction(correct:number,total:number){return total?`${correct} / ${total}`:'Not tested'}

export function EvaluationSummary({report:r}:{report:EvaluationReport}){
 const relevantTotal=r.relevance.tp+r.relevance.fn;
 const cards=[
  {value:fraction(r.relevance.tp,relevantTotal),title:'Financial messages found',description:`${r.relevance.fn} financial messages missed. ${r.relevance.fp} unrelated messages incorrectly saved.`},
  {value:fraction(r.explicit_amount_currency_role_exact_match.correct,r.explicit_amount_currency_role_exact_match.total),title:'Amounts read correctly',description:'Checks the amount, currency and what the amount means, such as purchase or minimum due.'},
  {value:fraction(r.explicit_event_date_exact_match.correct,r.explicit_event_date_exact_match.total),title:'Written dates read correctly',description:'Checks dates stated in messages. Missing dates stay unknown.'},
  {value:fraction(r.auto_validated_critical_accuracy.correct,r.auto_validated_critical_accuracy.total),title:'Checked fields in complete records',description:'Checks labelled amounts, types, status and dates in records the parser marked complete. Other fields may still need review.'},
 ];
 return <section className="evaluation-summary" aria-label="Quality check results">
  <h3>How the message checks performed</h3>
  <p>Tested using {r.count} made-up messages. This sample was used to find and fix bugs, so these are regression results. Your personal messages may perform differently.</p>
  <div className="evaluation-stats">{cards.map(c=><div className="evaluation-stat" key={c.title}><strong>{c.value}</strong><span>{c.title}</span><p>{c.description}</p></div>)}</div>
  <div className="evaluation-note"><strong>What this means for you</strong><br/>Use the saved records as a starting point. Check important amounts against the source evidence, and use Needs attention to resolve missing or conflicting details. “Complete” means the parser found its required fields; it does not verify the bank or merchant.</div>
  <details><summary>More about these checks</summary><ul>
   <li>Message type score: {(r.classification.macro_f1*100).toFixed(1)}%. This balances performance across message categories, including rare ones.</li>
   <li>Duplicate matching: {fraction(r.duplicates.correct,r.duplicates.expected)} expected pairs found; {r.duplicates.predicted-r.duplicates.correct} incorrect pairs.</li>
   <li>Purchase-to-refund matching: {fraction(r.relationships.correct,r.relationships.expected)} expected links found; {r.relationships.predicted-r.relationships.correct} incorrect links.</li>
   <li>Matching checks contain very few examples. They cannot establish reliability for all messages.</li>
   <li>{r.provider.live_verified?'An AI provider was exercised during these checks.':'AI provider success and automatic inbox connections have not been verified.'}</li>
  </ul></details>
 </section>;
}

const outcomes=[
 ['processed','Messages checked','All messages in this import.'],
 ['retained','Financial messages saved','A message can support one or more financial records.'],
 ['reimported','Already imported','Kept once, so importing again does not add the same message.'],
 ['irrelevant','Unrelated messages skipped','No financial information found; contents discarded.'],
 ['otp','Security codes skipped','OTP contents discarded before financial processing.'],
 ['unresolved','Unclear messages skipped','Not enough evidence of financial activity; contents discarded.'],
 ['failed','Messages not processed','Try importing these messages again.'],
 ['provider_failures','Local processing used instead','AI processing was unavailable; local rules were used.'],
] as const;

export function ImportOutcome({job,reviewCount,onActivity,onReview}:{job:Job;reviewCount:number;onActivity:()=>void;onReview:()=>void}){
 const saved=job.counts.retained||0,failed=job.counts.failed||0;
 const title=job.status==='failed'?'Import could not finish':job.status==='partial'?'Import finished with some issues':job.status==='processing'?'Import in progress':'Import complete';
 return <section className="panel spaced" aria-label="Latest import results">
  <div className="panel-heading"><div><h2>Latest import results</h2><p>{new Date(job.created_at).toLocaleString('en-IN',{dateStyle:'medium',timeStyle:'short'})}</p></div><span className={'badge '+(job.status==='completed'?'green':'amber')}>{job.status==='completed'?<CheckCheck size={14}/>:<AlertCircle size={14}/>} {title}</span></div>
  <p className="outcome-summary">{saved?`${saved} financial message${saved===1?' was':'s were'} saved. ${reviewCount?`${reviewCount} record${reviewCount===1?' needs':'s need'} your review.`:'Open activity to see the supported details.'}`:(job.counts.reimported?'These messages are already in your activity.':'No new financial records were saved from this import.')}</p>
  <div className="outcome-grid">{outcomes.map(([key,label,help])=><div key={key}><strong>{job.counts[key]||0}</strong><span>{label}</span><small>{help}</small></div>)}</div>
  {(failed>0||job.status==='failed')&&<p className="panel-footnote">Import the file or message again to retry. Previously saved messages will not be added twice.</p>}
  {(saved>0||!!job.counts.reimported)&&<div className="outcome-actions"><button className="primary small" onClick={onActivity}>View financial activity <ArrowRight size={14}/></button>{reviewCount>0&&<button className="secondary small" onClick={onReview}>Review missing details <ArrowRight size={14}/></button>}</div>}
 </section>;
}
