# Small live pilot

The tested `proof-live.toml` runs one UK query for **creative production manager in United Kingdom**, reads at most five descriptions and enriches at most two accounts. Employer-site verification is off. Exact-name Meta search avoids a corporate-homepage dependency. The config uses existing Azure model access; change the provider explicitly if using direct OpenAI.

The completed live test produced one account, **The Perfume Shop**, with a real listing, 20 matched active ad records and three candidate contacts. It needed fixes and continuation; direct Meta and LinkedIn corroboration remained blocked. [Actual test report](VALIDATION.md) · [Brief](../examples/live-validation/the-perfume-shop.md).

```bash
python3 -m creative_signal doctor --config proof-live.toml
python3 -m creative_signal plan --config proof-live.toml
```

| Stage | Maximum scope |
|---|---|
| JSearch | One discovery page, at most five descriptions analysed |
| Model | Five calls; 20,000 source characters and 1,500 output tokens per call |
| Meta through Apify | Two actor starts, 25 records each; $0.145 enforced ceiling each, $0.29 total |
| Apify readback | Up to 16 status reads and six dataset reads |
| Blitz | Four calls; at most 40 employee records returned |
| Employer verification | Disabled; no careers-page calls |

The ad ceiling is provider-enforced. The other stages have call/record/token caps; their actual costs depend on the configured model and existing provider plans. JSearch's configured estimate is $0.005 for the request. No subscriptions or credits are purchased. The existing actor rate is $0.0058 per dataset record, including empty-page summary rows; optional enrichment is off.

A new execution makes fresh billable requests. Review its scope and budget before running:

```bash
python3 -m creative_signal run --config proof-live.toml --execute --output runs/pilot-001
```

Use the listing's exact responsibility quotes and date as hiring evidence. A qualifying research brief also requires explicit coordination scope, matching active Meta records, a relevant current-company person reported by the people provider and source-linked exports. Unknown employer joins or absent ad evidence go to review. An empty yield is not a successful workflow demonstration.

Technical completion and independent source corroboration are recorded separately. Review native ad records, current employment/remit and CreativeX customer/territory eligibility before using the brief for outreach. Five descriptions and one usable account demonstrate feasibility, not a stable yield or accuracy rate.

Native public-page research is a small-sample alternative, but does not exercise the automated adapters. Adyntel is an optional legacy adapter; there is no automatic fallback or subscription purchase. Earlier `proof.toml` and `proof-location.toml` preserve the older creative-operations queries; `proof-live.toml` is the successful test configuration.

No automatic retries occur. A timeout or uncertain receipt may already be billable; reconcile that run before resuming. The test recoveries reused received evidence and stayed inside the original two-actor allowance. Private recovery scripts are not an automatic-resume feature of the CLI. Widening the query, provider route or spend requires a reviewed execution scope.
