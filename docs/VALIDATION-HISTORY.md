> Historical record, superseded by [the current validation report](VALIDATION.md). Statements about incomplete stages below describe the earlier tests.

# Validation record — 17 September 2026

**Partial live proof. The full end-to-end test has not passed.** The corrected search produced a real employer-verified Estée Lauder Companies hiring signal. Its corporate Facebook page lookup reported zero ads, so contact enrichment was skipped. The shareable [partial brief](../examples/live-validation/estee-lauder.md) comes from these live responses; it is separate from the earlier manual list and the synthetic demo.

## Operator correction: use the listing as the hiring signal

The operator removed mandatory employer-website verification after this test. **The current default accepts the job listing itself**, retaining its source URL, posting date and quoted responsibilities. Careers-page retrieval, application-button checks and the second description analysis are off unless `checks.verify_employer = true` is explicitly set. Earlier employer-stage results below are historical, not current pass requirements.

All **36 offline tests pass**. The current demo reaches ads and people without employer verification. A network-blocked replay of the saved live listings used five existing model answers and zero careers-page reads; it reached the ad stage. That replay added no paid calls and does not change the previously incomplete live result. It stopped at the existing dataset-read cap before another actor could start.

Current pass criteria use relevant recent listing evidence, advertising evidence, a relevant provider-returned person and an exported useful brief. Employer-site confirmation is not required.

## What actually ran

| Stage | Observed result | Limit |
|---|---|---|
| First JSearch request | `creative operations`, UK, past month: authenticated response with no vacancies | Empty yield; no downstream calls |
| Approved corrected JSearch request | `creative operations in United Kingdom`, UK, past month: 10 vacancies | One page; five descriptions analysed |
| Azure model inference | Five discovery descriptions and one employer description processed live | One answer contained a non-exact quote and was quarantined |
| Employer verification | Estée Lauder Companies' exact vacancy, responsibility quotes, date and allowed application action confirmed | The other selected account was an aggregator with no established employer route |
| Meta lookup through Apify | Corporate website resolved its Facebook page; one actor succeeded and returned a summary reporting zero ads | This is the corporate page only; consumer-brand pages are unchecked |
| Native Meta spot-check | HTTP 403 | Provider result not independently confirmed in the native library |
| Blitz people lookup | Not reached; earlier account-authentication check succeeded | No named person or email was enriched |
| Export | One useful partial hiring brief; zero accounts ready for priority review | Final exports reprocessed saved live evidence after fixes, not a clean uninterrupted run |

No outreach, CRM changes, subscriptions or credit purchases occurred. No manual accounts were substituted into the live batch.

## The real discovered account

**Estée Lauder Companies — Head of Agency and Creative Operations, London.** The employer posting is dated 15 September 2026. Its public job-detail record explicitly reports that the application action is allowed for matching job ID `1168275510450`.

The [employer posting](https://careers.elcompanies.com/careers/job/1168275510450-head-of-agency-and-creative-operations-london-gb-lnd-united-kingdom?domain=elcompanies.com) says:

> Create effective ways of working, governance and decision-making across the content ecosystem.

> Lead the transformation of the UK&I content operating model, translating global principles into a clear and locally relevant approach.

> Reporting to the VP, Enterprise Marketing & Data

This is a specific creative-governance conversation opportunity. It does not establish missing software, purchase intent, budget, CreativeX customer eligibility or the name of the responsible person.

The corporate website links to [The Estée Lauder Companies on Facebook](https://www.facebook.com/esteelaudercompanies). The live actor resolved page ID `309210685774788` and returned `totalCount: 0`, `results: []`, and a complete page-summary flag. This is **one summary row, zero ad records**. It does not describe the group's other brand pages.

The corporate [Estée Lauder brand page](https://www.elcompanies.com/en/our-brands/estee-lauder) links to `esteelauder.com`, establishing an owned consumer brand. Attempts to retrieve the consumer-brand homepage returned HTTP 403, so no consumer-brand Facebook mapping was established or sampled. Expanding to owned brand pages is the concrete next workflow improvement; an unverified name match must not be used as a substitute.

## Fixes driven by actual responses

1. **Empty completion was ambiguous.** Reports now distinguish execution completion from yield. Zero qualifying briefs produces `failed_yield` and CLI exit 3. Candidate briefs still need independent checks before proof passes.
2. **One quote could halt the batch.** Paddle's model answer added literal quotation marks around a source excerpt. It failed exact validation. Completed invalid answers now go into review without retries; other accounts can continue. Timeouts and incomplete responses still halt.
3. **The employer used a dynamic application control.** The HTML contained the matching JobPosting but no rendered application button. The verifier now checks the identified Eightfold interface's public `position_details` record, requiring matching employer, ID, title, public URL and an explicitly allowed application action.
4. **Apify metadata lagged the dataset.** Immediately after success, metadata said zero rows while the item response contained one. A later readback confirmed one row. The adapter now permits one metadata readback inside the existing cap; persistent mismatches halt, and insufficient remaining dataset-read capacity prevents another actor start.
5. **No ads still produced a record.** The adapter now recognises the actor's validated empty-page summary without treating it as an ad. Empty, unresolved and actively advertising pages stay distinct.

At that checkpoint, **35 offline tests passed**, including these cases, identity mismatches, wrong employer/job IDs, denied application actions, former employees, caps and uncertain requests. Offline tests validate handling, not live lead yield. The live fixture replay is explicitly labelled `live_evidence_replay` and made no network calls.

## Execution and recovery provenance

- `runs/live-proof-20260917-apify-01/`: first live query, zero results.
- `runs/live-proof-location-20260917-01/`: approved corrected query and first five real model responses; stopped on non-exact quote.
- `runs/live-proof-location-20260917-01-continued/`: reused those received responses, without new discovery/model charges for them; fetched employer pages and the sixth model answer.
- `runs/employer-eightfold-*/`: saved public script, employer search and matching job-detail evidence used to diagnose the application control.
- `runs/live-proof-location-20260917-01-eightfold/`: reused received employer/model evidence, then started the single real Apify actor. Stopped on dataset-count inconsistency.
- `runs/live-proof-location-20260917-01-reconcile/`: read back the same actor and dataset; no replacement run.
- `runs/live-proof-location-20260917-reviewed/`: final normal pipeline reprocessing of actual saved responses after fixes. All inputs trace to live sources; no synthetic or manually supplied accounts. Network access was blocked for this replay.
- `runs/live-proof-location-20260917-native-check/`: native Meta HTTP 403.

The recovery scripts are private and scoped to these exact receipts. The portable CLI does not silently resume or replay paid requests. These recoveries demonstrate corrected handling of real responses; they do not satisfy the requirement for a clean live end-to-end pass.

## Actual usage

Across both searches: two JSearch requests, estimated **$0.01** at the configured rate; actual JSearch billing has not been reconciled.

The corrected batch used six Azure responses: **6,560 input tokens and 1,194 output tokens**. Azure currency cost is not established by the configured rates.

Meta: **one actor start**, two status reads and three dataset reads. Readback reported **$0.0058**, with one billed dataset event and zero enrichment events. The actor charged for the zero-ad summary row. The enforced ceiling was $0.145; no second or replacement actor started.

There were **12 public requests including diagnostics, native verification and brand-mapping review**, within the 14-request scope. Blitz employee-lookup calls: **zero**. Replaying saved responses added no acquisition charges. No wider search or additional paid sample has run.

## Historical pass criteria used for the original test

At least one account must supply all of the following from the live workflow: discovered vacancy and employer identity; matching current employer evidence with exact quotes; active ads tied to a verified owned advertiser and landing domain; a relevant current person returned by the contact provider; and an exported useful brief. Native ad and current-role checks must corroborate the material outputs.

This sample has employer evidence but no active ads on the chosen page and no contact result. Do not present it as a passed full workflow. The operator subsequently removed the employer-verification gate as recorded above. A broader or brand-aware paid sample requires a revised execution proposal under the repository policy.

## Where the five accounts came from

These were selected through public web research, not imported from JSearch or injected into a live pipeline run.

| Account | Primary vacancy source | Latest employer-stage result |
|---|---|---|
| SharkNinja | [Employer posting](https://careers.sharkninja.com/job/irvine/associate-creative-director/47204/99808760656) | Matched posting, application offered, date parsed |
| LEGO Group | [Employer posting](https://www.lego.com/en-gb/careers/job/sr-brand-strategist-cd8eec714ca610022b35d1c091ba0000) | Matched posting, application offered, date parsed |
| Nike | [Employer posting](https://careers.nike.com/manager-creative-production-hk-gc/job/R-90345) | Matched posting, application offered, date parsed |
| Ancient + Brave | [Employer posting](https://careers.ancientandbrave.earth/jobs/8388641-uk-creator-manager) | Matched posting, application offered, date parsed |
| Gymshark | [Employer-linked vacancy](https://job-boards.eu.greenhouse.io/gymshark/jobs/4793583101) | Corporate careers page confirms the application link, but the page lacks a matching structured posting supported by the parser |

The initial SharkNinja sheet used the descriptive label “Associate Creative Director, Content Studio”; the employer's actual heading is “Associate Creative Director”. The repeat probe used the actual heading; title matching was not loosened. Gymshark required its known corporate careers-index URL because its bare domain redirected to a checkout page. That reviewed seed is not automatic careers discovery.

The named people in the original sample came from employer pages: Jad Jichi on SharkNinja's creative careers page, Julia Goldin on LEGO's leadership page, and Noel Mack on Gymshark's About page. They were not returned by Blitz, and they are not all confirmed operational owners.

## Earlier manual employer-stage probes

The original five-account shortlist was researched manually on 17 September. Four postings passed employer-stage checks after date and application-control fixes; Gymshark's structured posting remains unsupported. These probes do not establish end-to-end acquisition.

Private probe directories: `runs/employer-probe-20260917T212104Z/` and `runs/employer-probe-20260917T212357Z/`. Their records are labelled `live_employer_stage_only`. The included `examples/demo/` is entirely synthetic; `examples/live-validation/` contains the separate partial result from the actual corrected query.
