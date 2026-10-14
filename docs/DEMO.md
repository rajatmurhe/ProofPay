# Five-minute demo

Start both local services. All actions below use synthetic messages, never a personal inbox.

0:00 — Connect & import. If seeded, delete local synthetic data using the explicit confirmation. Explain local processing and demo message labels. Expand the golden journey, click **1. Purchase + email**.

0:40 — Financial activity. Open Amazon. Show INR 1,499, the shared reference and two masked evidence sources (SMS and email). Raw bodies are absent. Net purchase remains INR 1,499.

1:15 — Import, **2. Refund initiated**. Bills & refunds now shows pending INR 499 and unchanged purchase net. Then **3. Refund received**. Inspect purchase: received INR 499, pending zero, net INR 1,000. Re-clicking stages does not duplicate retained messages.

2:00 — **Load synthetic demo**. Show aggregate counts for irrelevant, OTP and unresolved content. Upload `data/synthetic/purchase.eml` or `sample.csv` to demonstrate the actual file adapter; both work without accounts. New evidence may be retained, but referenced purchase spending is not duplicated.

2:40 — Needs attention. Open a Corner Cafe suggestion; similar merchant/amount/date is only a proposed duplicate. Accept or reject it; use Undo on an accepted link to restore distinct events. Never accept a link merely to make totals smaller.

3:20 — Open a purchase and correct its Category with a reason. Close the dialog and inspect the updated category breakdown. Reopen to inspect correction history and preserved observed source evidence. Dashboard tiles open contributing activity.

4:10 — Bills & refunds. Distinguish total due, minimum due and due date. Explain message coverage, unknown instrument identity, unresolved currencies and the absence of a complete outstanding balance claim.

4:35 — Connect & import → **View quality check results**. Show the readable cards for messages, amounts and dates. Explain that the 50 made-up messages were used to find and fix bugs, so the results are regression checks rather than a guarantee for personal messages. AI provider success and inbox connections remain unverified. Finish with local-data deletion if desired.
