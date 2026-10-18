"""Synthetic classification corpus. Split whole wording templates, never rows."""
import json
from pathlib import Path

# First 3 templates train, fourth validates, fifth tests. Fixed before training.
TEMPLATES = {
 'Transaction': [
 'Spent INR {amount} at {merchant} using your card.',
 'Your account was debited INR {amount} for a purchase at {merchant}.',
 'Paid INR {amount} to {merchant}. Transaction successful.',
 'Purchase confirmed at {merchant}: INR {amount} charged to card.',
 'A debit of INR {amount} towards shopping at {merchant} is complete.'
 ],
 'Payment': [
 'Credit card payment INR {amount} received. Thank you.',
 'Transferred INR {amount} from your account to {merchant}.',
 'Your card bill payment of INR {amount} was successful.',
 'We received INR {amount} towards your credit card balance.',
 'INR {amount} has been applied to settle your card dues.'
 ],
 'Refund': [
 'Refund INR {amount} credited for your order at {merchant}.',
 'Your refund of INR {amount} from {merchant} is pending.',
 '{merchant} initiated a refund of INR {amount} to your account.',
 'Your return at {merchant} was processed. Refund amount: INR {amount}.',
 'Money back for the returned item: INR {amount} from {merchant}.'
 ],
 'Credit Card Bill': [
 'Credit card statement total due INR {amount}, minimum due INR 100.',
 'Your card bill is ready. Please pay INR {amount} by 2026-11-05.',
 'Credit card outstanding bill INR {amount}. Minimum payment INR 100.',
 'Monthly card statement generated. Amount payable INR {amount}.',
 'Billing cycle closed. Your credit card dues total INR {amount}.'
 ],
 'Cashback/Reward': [
 'Cashback INR {amount} credited to your wallet.',
 'You earned reward points for shopping at {merchant}.',
 'Your cashback of INR {amount} is pending.',
 'Loyalty reward INR {amount} added after your purchase.',
 'Enjoy INR {amount} back as a shopping reward from {merchant}.'
 ],
 'EMI': [
 'EMI INR {amount} debited for your loan.',
 'Your monthly loan installment of INR {amount} is due.',
 'EMI payment INR {amount} received for the current month.',
 'Scheduled installment INR {amount} will be collected for your loan.',
 'This month loan repayment: INR {amount} under your EMI plan.'
 ],
 'Failed Transaction': [
 'Payment INR {amount} failed at {merchant}.',
 'Your card transaction for INR {amount} was declined.',
 'UPI transfer INR {amount} unsuccessful. Please retry.',
 'Unable to process your purchase of INR {amount} at {merchant}.',
 'Transaction rejected for insufficient funds. Amount INR {amount}.'
 ],
 'Offer/Promotion': [
 'Offer: save INR {amount} on your next purchase at {merchant}.',
 'Get discount INR {amount} when you shop with your card.',
 'Limited promotion from {merchant}: coupon worth INR {amount}.',
 'Shop today at {merchant} and unlock a discount of INR {amount}.',
 'Sale announcement: use coupon SAVE for INR {amount} off your order.'
 ],
 'OTP': [
 'OTP {code} to approve card payment INR {amount}. Do not share.',
 'Your one time password is {code}.',
 'Verification code {code} for your account sign in.',
 'Use authentication code {code} to confirm INR {amount}.',
 'Security code {code} expires in five minutes. Never disclose it.'
 ],
 'Other': [
 'Meet me at {merchant} after lunch.',
 'Our class will discuss bank loans and payment systems today.',
 'The invoice design workshop starts tomorrow.',
 'Can you review the refund policy draft for our project?',
 'The bank branch is closed on Sunday. Visit on Monday.'
 ]
}

def build():
 rows=[]
 for kind,templates in TEMPLATES.items():
  for t,template in enumerate(templates):
   split='train' if t<3 else 'validation' if t==3 else 'test'
   for i,(amount,merchant) in enumerate([(125,'Aster Books'),(499,'Maple Market'),(1499,'Nimbus Store'),(8200,'Cedar Services')]):
    family=f'{kind}:{t}'
    rows.append({'id':f'{family}:{i}','family':family,'split':split,'provenance':'synthetic','body':template.format(amount=amount,merchant=merchant,code=730100+i),'label':kind})
 return rows

if __name__=='__main__':
 rows=build();path=Path(__file__).with_name('corpus.json')
 path.write_text(json.dumps(rows,indent=2)+'\n');print(f'{len(rows)} synthetic examples, {len(TEMPLATES)*5} template families')
