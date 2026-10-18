# ProofPay: evaluation and automation upgrade

ProofPay turns financial messages into evidence-linked records for purchases, bills, payments and refunds. This upgrade adds a reproducible ML experiment, explicit rules/LLM/hybrid evaluation, and durable Gmail imports. It runs locally without a paid AI provider. Public hosting and real Google OAuth activation remain separate setup steps.

## What the upgrade demonstrates

| Role | Implemented evidence |
| --- | --- |
| AI/ML internship | Template-family data splits, TF-IDF + logistic regression, per-class metrics, confusion matrix, validation-selected review threshold, JSON model artifact, and leakage tests |
| AI automation | User-triggered Gmail tasks, persistent queue, bounded retries, restart recovery, replay deduplication, account/session checks, and progress in the UI |
| Forward deployed engineering | Existing customer-facing import/review workflow, explicit failure messages, private account boundaries, PostgreSQL migrations, container stack, CI, and an operational handoff |

The classifier is an offline experiment. It does not replace the rules extractor or automatically change financial records. The optional LLM comparison is also an offline synthetic-data experiment; Gmail imports continue using local rules.

## Reproduce locally

From the repository root, using Python 3.12:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r services/api/requirements.lock -r ml/requirements.lock
.venv/bin/python ml/train.py
.venv/bin/python evaluation/compare.py
PYTHONPATH=services/api .venv/bin/python -m pytest services/api/tests ml/tests -q
```

`ml/build_corpus.py` regenerates the checked-in synthetic corpus. Training emits `ml/reports/classifier-report.json` and the ignored local `classifier-model.json`. The report includes the corpus SHA-256, dependency version, hyperparameters, split counts and limitations. The weights use JSON, not executable pickle.

To try the classifier without saving input text:

```bash
printf '%s' 'Refund INR 125 credited for your order at Aster Books.' | .venv/bin/python ml/predict.py
```

The output is a label, an uncalibrated score and a review flag. A local OTP gate precedes classification. This command does not import messages or save financial facts. Use synthetic text for demonstrations.

## Dataset and results interpretation

The new corpus contains 200 agent-authored synthetic examples across 10 classes and 50 wording families: 120 training examples, 40 validation examples and 40 test examples. Whole templates stay in one split; the validator rejects cross-split families and normalized identical text. Vocabulary and IDF are fitted on training data only. A fixed threshold grid is searched on validation data for at least 90% accuracy among accepted predictions, choosing maximum coverage. If no threshold qualifies, the model abstains.

The first run achieved **0.733 macro F1**, **80% overall accuracy**, and a **70% review rate** on the 40-example test split. The remaining 12 predictions were correct in this small synthetic sample. This is not a claim of 100% production accuracy: validation and test each contain only one wording family per class. Transaction and promotion wording produced errors. The rules baseline scored **0.120 macro F1** on exactly the same test cases, mapping messages without extracted events to Other. The learned classifier improved this synthetic classification result, but has not been evaluated for extracting amounts or dates. Compare those two scores within this corpus, not against scores from another dataset.

The separate extraction comparison uses the existing 50-case synthetic regression suite. Rules achieved 50/50 relevance decisions, 35/35 relevant-message amount-list matches, and 8/8 labeled-date matches. Its perfect classification score is a regression result on known fixtures, not unseen-mail generalization. Reports explicitly mark LLM and hybrid strategies **not run** until configured and opted in. Once a test report has been inspected, treat it as development evidence and reserve fresh, independently labeled data for a final evaluation.

### Optional live comparison later

Configure `AI_BASE_URL`, `AI_MODEL` and `AI_API_KEY` in your shell or secret manager. Do not commit keys. The runner accepts an HTTPS chat-completions endpoint and only submits this repository's synthetic fixture. It never reads your mailbox.

```bash
.venv/bin/python evaluation/compare.py --allow-live-synthetic --max-calls 50
```

The call budget applies separately to LLM and hybrid, so this command allows at most 100 provider attempts overall. Supply `--input-usd-per-million` and `--output-usd-per-million` using your provider's rates to calculate token cost. Without rates or complete usage, cost is `null`, not an invented number. Latency is measured locally and is hardware/network dependent; it is not a production SLA.

Every strategy uses the local OTP gate. LLM output must pass a strict fact schema and lexical checks for amount, currency, evidence and date. Grounding does not prove semantic correctness. Provider failures are counted; hybrid rule fallback is explicit. All model-derived facts require review. Reports record fixture IDs and normalized predictions, not raw provider responses, credentials or message bodies.

## Gmail worker behavior

Apply migrations and start the API/web as described in the main README. Start the worker in a third terminal with the same database and connector environment:

```bash
.venv/bin/python -m alembic -c services/api/alembic.ini upgrade head
./scripts/gmail-worker.sh
# Single pass for operational checks:
./scripts/gmail-worker.sh --once
```

The wrapper reads the ignored root `.env`. Set `PROOFPAY_PYTHON=.venv-ai/bin/python` if using that local environment. The Python worker itself does not load `.env`; containers inject their environment directly.

A user chooses a bounded date window and consents to each batch. The UI submits `POST /connectors/gmail/imports` and polls account-private status. The existing synchronous route remains available. Each UI request reads up to 20 matching emails; the server maximum is 50. A next-page cursor remains date/account/connection bound. This is a durable **user-requested batch**, not an unattended recurring inbox sync.

One active task is allowed per account. A conditional database claim prevents two workers processing the same task at once. A 20-minute lease permits recovery after a crash; at most three attempts are allowed. Temporary failures retry after 30 and 60 seconds. After a crash the Gmail connection's 15-minute lock expires before the task lease. Replay protection prevents already saved messages being added twice.

The worker rechecks account status, session expiry and the connection generation. Sign-out or disconnect stops pending retention. Data deletion removes task metadata and rotates the generation, so old fetched batches cannot repopulate the workspace. Retention is committed in one transaction serialized against connection deletion/change. Terminal tasks discard request parameters. Queue results contain counts and identifiers, not raw mail. Existing financial-message retention remains masked evidence only.

Keep signed in while an import runs. With no worker running, the UI honestly displays queued. The worker reports sanitized errors; monitor process availability and task age operationally. Failed imports require a fresh explicit request after three attempts. Google setup, OAuth consent and live mailbox verification have not been performed as part of this upgrade.

## Interview walkthrough (two minutes)

1. Show a synthetic import, inspect its evidence, correct a field and export the result.
2. Explain why deterministic money parsing and an OTP gate precede optional AI assistance.
3. Open the classifier report: describe the grouped splits, validation threshold, confusion matrix, errors and high review rate. State that it is synthetic, experimental evidence.
4. Show the Gmail queue test/demo and explain restart recovery, deduplication and cancellation. The committed screenshot uses a mocked connector response, not a real inbox.
5. Show the Compose stack and CI workflow. State the remaining provider/hosting steps honestly.

A defensible summary: “I built ProofPay, an evidence-linked financial-message application, and added a reproducible classifier experiment and a durable import workflow. I measured errors and review coverage instead of assuming AI output was correct, and kept sensitive message processing local.”

## Next evidence to collect

Obtain consented, de-identified examples with independent labels and more template/provider diversity; hold out a fresh test set. Measure calibration and review workload before changing the decision policy. Activate a Google test OAuth client, verify revocation and real MIME coverage, then evaluate a chosen LLM within a cost budget. Choose hosting, configure HTTPS/secrets/backups, and exercise restore and incident procedures before any production claim.

Methodology reference: [scikit-learn's guidance on leakage and pipelines](https://scikit-learn.org/stable/common_pitfalls.html).
