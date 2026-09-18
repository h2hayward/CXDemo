# Live validation — 18 September 2026

**The live integration test completed for one discovered account, The Perfume Shop.** Job discovery, model analysis, Meta sampling, person lookup and export all used real provider responses. This required fixes and continuation of the same batch; it was not an uninterrupted first-attempt run. Final presentation and contact ranking were refreshed locally without new acquisition.

[Account brief](../examples/live-validation/the-perfume-shop.md) · [Lead list](../examples/live-validation/leads.csv) · [Evidence and receipts](../examples/live-validation/evidence/provenance.json)

## Observed results

| Stage | Actual result |
|---|---|
| Job discovery | One live UK search for `creative production manager in United Kingdom`, past month; ten returned vacancies |
| Responsibilities | Five live Azure analyses; one qualified advertiser, three rejected records and one intermediary held for review |
| Hiring evidence | The Perfume Shop, Design Operations & Production Manager, posted 9 September 2026; listing description, URL, date and exact quotes retained |
| Initial ad lookup | Homepage requests returned 403; broad company-keyword Meta search returned 25 unrelated records, none promoted |
| Exact-name Meta lookup | Same Apify actor, second bounded run: 25 rows, 22 unique active ads, 20 unique active ads matching advertiser name/ID and the company destination domain |
| People | Live Blitz company resolution plus employee finder; 14 employee records, six relevant current-domain candidates, three selected |
| Export | One complete account brief and CSV lead; another account held for unresolved employer identity |
| Native spot-check | Meta 403; LinkedIn 999. Independent corroboration remains incomplete |

The user explicitly accepted the job listing as hiring evidence. **No employer-site verification was required or performed for the successful batch.** The earlier homepage fetches were attempts to identify the advertiser page, not checks on the vacancy.

The listing states:

> Oversee the end-to-end creative production process, ensuring work is accurately briefed, tracked, quality checked and delivered to a high standard.

> Coordinate production activity across online, social, CRM, print, campaign and in-store channels.

The selected people are Jona McKnight (Senior Creative and Production Manager), Amy Danbrowsky (Senior Brand & Insights Manager) and Amy Sawyer (Senior Digital Marketing and Analytics Manager). These are provider-reported current roles. Their remit, reporting relationships and CreativeX account eligibility need review.

## What passed and what remains unverified

The technical workflow passed: a company emerged from the live discovery query, its quoted responsibilities qualified, live ad records matched the company, the live people provider returned relevant professional profiles, and export produced a usable brief. No manually researched account or synthetic record was substituted.

The ad sample is not an account-wide inventory. No ad spend, performance, missing software, buying intent or prospect eligibility is established. Direct native ad/person corroboration was blocked. The manifest therefore retains `pending_independent_checks` for the live run and does not certify the account for outreach.

The completed live run is `runs/fresh-live-test-20260917-01-exact-search/`. Final local reprocessing is `runs/fresh-live-test-20260917-final/`; it is explicitly labelled `live_evidence_replay` with network access blocked. The successful live run already contained every stage before that reprocessing. The portable CLI does not implement automatic recovery or silently repeat failed paid calls.

## Fixes demonstrated by real responses

- Reserved up to three dataset reads per actor, preventing the old read cap from interrupting inspection of the second run.
- Added exact-phrase company search in Meta Ad Library, avoiding the corporate-homepage dependency. Broad unordered search was too noisy and is no longer used by this mode.
- Required exact normalized advertiser-name matching, consistent numeric page IDs, an explicit active flag and a matching destination domain. Unrelated advertisers remain excluded.
- Handled delayed dataset metadata: it reported 20 while the items endpoint returned 25. Both were inside the cap; observed rows were retained with the mismatch recorded. Later readback confirmed 25 for both runs. Oversized or missing records still halt.
- Ranked creative production/operations roles ahead of broad brand roles for the governance signal, including titles such as “Creative and Production Manager”.
- Used the returned job-board URL in the brief and cleaned up the generated conversation question.

**41 offline regression tests pass.** A final network-blocked run through the same pipeline confirmed the source quotes, 20 matched ads, three candidates, strongest contact and direct listing link. These checks accompany the completed live integration; they are not a substitute for it.

## Acquisition and cost

This fresh batch used **one JSearch request, five Azure model calls, two Apify actor starts and two Blitz calls**. The model used 5,597 input and 1,032 output tokens. JSearch's configured estimate is $0.005; Azure and JSearch billed currency totals were not independently reconciled. Blitz used the existing account and returned 14 employee records plus one company resolution.

Apify readback confirmed **$0.145 per run, $0.29 total**, with 25 billed dataset events per run and no optional enrichment events. Both used build `0.0.378`, a 25-record limit and a provider-enforced $0.145 ceiling. No subscriptions, credits or outreach were purchased or sent.

| Lookup | Actor run | Final dataset count | Charge |
|---|---|---:|---:|
| Broad keyword, no matching ads | `dc3hSQAHiYvarPlq1` | 25 | $0.145 |
| Exact company phrase, qualifying ads | `EkPFxkQRMlPWxqHYc` | 25 | $0.145 |

## Recovery provenance

- `runs/fresh-live-test-20260917-01/`: original live job query and five model responses; homepage ad-page discovery blocked.
- `runs/fresh-live-test-20260917-01-meta-search/`: reused those received job/model responses, then made the first live ad request; halted on delayed metadata.
- `runs/fresh-live-test-20260917-01-meta-readback/`: same actor reconciled; no replacement.
- `runs/fresh-live-test-20260917-01-exact-search/`: reused the same job/model evidence, ran the approved second Meta sample and both live Blitz calls; completed and exported one priority-review account.
- `runs/fresh-live-test-20260917-01-exact-readback/`: confirmed successful actor, 25 records and $0.145 charge.
- `runs/fresh-live-test-20260917-01-native-spot-check/`: recorded blocked Meta/LinkedIn checks.
- `runs/fresh-live-test-20260917-final/`: network-blocked local reprocessing after ranking and presentation fixes.

Private raw responses remain in ignored run folders. The shareable example contains only selected relevant fields, professional contacts, source links, receipts and original response hashes.

The earlier Estée Lauder partial test, employer-verifier probes and five manually researched accounts remain documented in [validation history](VALIDATION-HISTORY.md). They are not added to this run's lead yield or cost. The included `real-sample/` ZIP content is the earlier manual research; `examples/live-validation/leads.csv` is the new workflow result.
