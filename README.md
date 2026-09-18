# CXDemo

Turn a relevant vacancy into an account research brief: what the company is hiring someone to do, why that could relate to CreativeX, whether Meta advertising is visible, and who might own the work.

This is a standalone Python command-line workflow built as a CreativeX research proof of concept. It removes repetitive SDR research and leaves a small, inspectable queue for a person to review.

Start with the [live test and account tables](EXAMPLE.md), [full account brief](examples/live-validation/the-perfume-shop.md) or [CSV lead list](examples/live-validation/leads.csv).

**Live test completed:** a UK job search found The Perfume Shop's Design Operations & Production Manager vacancy; the workflow matched **20 active Meta ads** and selected **three contact candidates** from a live people lookup. [Read the brief](examples/live-validation/the-perfume-shop.md) or [open the lead list](examples/live-validation/leads.csv).

The batch completed after fixes and resuming received responses. Current roles and ad activity are provider-reported; direct Meta/LinkedIn spot-checks were blocked. This proves the integrations and export path, with independent source corroboration still pending. The sample is separate from the older manual research and synthetic demo. [Full validation](docs/VALIDATION.md).

## Try it in a minute

Requires Python 3.11 or later. No runtime packages or API keys are needed for the demo.

```bash
python3 -m creative_signal demo --output runs/demo
```

Open `runs/demo/report.md`. It links to one brief per account and explains every rejected, excluded or unresolved vacancy. Choose a different output directory when rerunning.

Prefer to read the result first? Open the [included demo report](examples/demo/report.md) and [two-minute walkthrough](docs/DEMO.md).

The fixture contains eight discovery records. The run produces two priority-review accounts, rejects a physical-product-design role and a stale listing, removes a duplicate, honours an exclusion, and exposes missing domain/ad evidence.

## What it does

```text
JSearch vacancy discovery
  → remove duplicates and excluded accounts
  → read responsibilities, not just job titles
  → use the listing description, source URL and posting date
  → search Meta for the exact company name and sample up to 25 active ads
  → find up to three possible functional owners
  → export an account queue, briefs and supporting evidence
```

| Stage | Useful output | Important limit |
|---|---|---|
| JSearch | Candidate vacancies for creative operations, production and effectiveness | A third-party Google for Jobs/job-board aggregator, not an official Google Jobs API |
| Job listing + model analysis | Responsibility quotes, coordination scope and any stated reporting relationship | Hiring evidence comes from the listing; a job title alone does not qualify |
| Apify / Meta | Active records matching advertiser identity and the account's landing domain | Up to 25 ads/account; total inventory stays unknown; no advertiser-spend inference |
| Blitz | Possible owners with provider-reported current employment at the matched domain | Current remit and the vacancy's reporting relationship remain unconfirmed |
| Brief | Evidence, CreativeX relevance hypothesis, people, conversation direction and next action | Account/customer status and territory ownership still need CreativeX's own records |

The initial qualification is deliberately narrow: an own-brand advertiser hiring for advertising governance or creative measurement, with explicit coordination across markets, brands, channels or teams. A footwear designer, generic content creator or agency hiring for an unnamed client does not qualify for this version.

## Outputs

- `report.md`: readable account queue and vacancy decisions.
- `briefs/*.md`: exact evidence, possible owners, conversation angle, a draft question anchored in a listing quote, and unresolved checks.
- `accounts.csv`: ranked review queue with hiring-source URL/type; `employer_url` stays blank when no employer website was checked. Unsafe spreadsheet formula prefixes are escaped.
- `results.json`: all jobs, dispositions, quotes, ad counts and contact candidates.
- `manifest.json`: configuration, caps, usage, execution state and separate yield/validation outcome.
- `evidence/` and `receipts/`: saved provider responses, employer pages and call outcomes.

A completed model answer with invalid quotes is held for review without retrying it; other candidates can continue. Uncertain requests still halt the run. A delayed Apify dataset count is re-read once without starting another actor. Bounded observed records can proceed with the lag recorded; later readback reconciles cost and final metadata.

A completed execution is not a passed proof. An empty run is marked `failed_yield` and exits with code 3; a halted run exits with code 2. An exit code of 0 with candidate briefs still requires independent ad/person checks.

An account marked `priority_review` has passed the evidence gates and has a possible functional owner. It is not send-ready. Scores count eight transparent evidence points; they do not estimate purchase likelihood. Exact thresholds are in [the MVP specification](docs/MVP.md).

## Configure a live run

Copy `.env.example` to `.env` and enter your own credentials. This file belongs beside the TOML configuration; credentials are never embedded in the portable project. The tested `proof-live.toml` uses Azure and its `AZURE_OPENAI_*` variables. To use direct OpenAI, set `analysis.provider = "openai"` and supply `OPENAI_API_KEY` and `OPENAI_MODEL`. The model must support Responses structured outputs.

```bash
cp -n .env.example .env
python3 -m creative_signal doctor --config proof-live.toml
python3 -m creative_signal plan --config proof-live.toml
```

`doctor` checks variable presence locally; it does not validate credentials. `plan` and `run` without `--execute` make no network calls.

Review [provider setup, scope and costs](docs/PROVIDERS.md) and the [first live pilot](docs/PILOT.md). Once the operator has approved the acquisition scope and budget:

```bash
python3 -m creative_signal run --config proof-live.toml --execute --output runs/live-001
```

**Employer website verification is off by default.** A relevant recent job listing is sufficient hiring evidence. Its source URL and date are retained in the brief; the workflow proceeds to ads and people without fetching the careers page or analysing the description a second time. Set `checks.verify_employer = true` only if that extra check is wanted.

The small `proof-live.toml` run uses one UK query, five descriptions and two accounts. Its Apify ceiling is $0.145/account ($0.29 total), enforced through the provider's run API; no subscriptions or credits are purchased. `APIFY_TOKEN` replaces the Adyntel credentials for this route. Other provider calls still have their own costs.

The larger `mvp.toml` configuration has three queries in the US and UK, one page each, at most 30 descriptions and 10 accounts; it needs its own larger acquisition scope. Ad and people lookups happen only after earlier checks pass.

Use `accounts.include_domains` for a named-account list, and `exclude_domains` for customers or other exclusions supplied by the operator. The workflow cannot infer CRM eligibility from public evidence. Reviewed aliases and hosted careers routes can be configured explicitly; no fuzzy company-name joins are used.

The tested config sets `checks.ad_lookup = "company_search"`: an exact-phrase Meta search with matching advertiser name, consistent page IDs, explicit activity and matching company destination domain. This avoids a homepage dependency but does not independently prove page ownership. The optional `corporate_page` mode resolves a page from the homepage or an explicit reviewed `[checks.facebook_pages]` mapping; missing or multiple pages remain unresolved.

## Test or install

```bash
python3 -m unittest discover -s tests -v
```

Tests block network access for the full demo and cover evidence validation, expiry, wrong employers, ad-count ambiguity, former employees, exclusions, caps, partial failures, escaping and CLI execution gates. Scripted model responses test the workflow; they do not measure live model accuracy.

Optional installation adds the `creative-signal` command:

```bash
python3 -m pip install .
creative-signal demo
```

Installation may download the build tool; the workflow itself has no third-party runtime dependencies. A dependency-free invocation from this directory remains `python3 -m creative_signal`.

## Repository contents

The workflow runs independently of the original research workspace. `examples/demo/` contains synthetic demonstration data; `examples/live-validation/` contains selected evidence from the completed live test. Keep your own `.env` and `runs/` private. The supplied `.gitignore` excludes them, and GitHub Actions runs only the offline tests and demo.

The next useful extension is a scheduled run against an agreed named-account list with cross-run change tracking and CRM suppression. The [MVP specification](docs/MVP.md) explains the boundary; this release does not schedule jobs, modify a CRM, enrich email addresses or send outreach.

## A daily version

The next step would be a scheduled morning run against agreed markets or target accounts, with a digest of fresh qualifying accounts. Scheduling, change tracking across runs, digest delivery and CRM suppression are not enabled in this demo. The core discovery, ad sampling, people lookup and file export have been exercised live.
