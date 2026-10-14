# Metric semantics

All money is integer minor units. INR is the selected demo currency, not an inferred currency. Other explicit currencies remain separate. `$` alone is unresolved; no conversion or combined total exists.

- **Purchase spending:** completed (`successful`) purchase events, after accepted duplicate grouping. Excludes card repayments, transfers, failed/reversed/pending records, bills, offers, cashback and credits. Reviewable relevant records with explicit amounts may contribute; the attention count exposes uncertainty. Live provider suggestions are excluded from completed-purchase and received-refund totals.
- **Purchase-linked net:** original completed purchase minus completed accepted linked refunds, even if a refund arrives in another period. Initiated/pending refunds do not reduce it. Over-refunds are flagged rather than clipped to zero. This is not period cashflow.
- **Received refunds:** successful refund events with explicit selected currency. Includes unlinked refunds. Progress notices sharing a compatible explicit refund reference are one canonical event; completion wins over initiation.
- **Pending refunds:** initiated/pending canonical refunds, excluding completed progress groups. These do not change net spending.
- **Reported bills due:** total-due amounts from imported statements; minimum due is separate. There is no balance reconciliation or inference that a statement has been paid. Repeated monthly statements can coexist. This is explicitly not a complete outstanding balance.
- **Category/instrument breakdown:** gross completed purchase amounts. Category describes merchant business, not purchased items. Instrument descriptors do not establish unique account identity.
- **Cashflow API fields:** successful events explicitly assigned account inflow/outflow, not card liability. A credit is not labelled income. Cashflow is available in `/metrics`, not a second decorative dashboard chart.
- **Needs review:** missing/invalid/conflicting facts or suggested relationships. No irrelevant messages, uncertain-relevance content or OTPs are queued here.

Date filters use observed event dates (ISO day precision); records missing dates are excluded only when a date filter is active. No received-date substitution. Refund period totals use refund completion dates. Source filters select events with a matching evidence source; a selected purchase's net includes all its accepted linked refund evidence. Every dashboard tile and category/instrument row opens its contributors. CSV/JSON exports deliberately export all structured records and say so in the UI.

Tests: `test_golden.py`, `test_domain.py`, and browser golden journey. Small integers remain below JavaScript's exact-integer limit; the API schema caps a single amount at 10^15 minor units. Very large aggregate portfolios are outside this bounded prototype.
