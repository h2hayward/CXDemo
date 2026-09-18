# Provider setup and current limits

Documentation checked on 17–18 September 2026. API and price details can change. JSearch, Azure inference, Apify and Blitz employee lookup have now run live; see [validation](VALIDATION.md) for actual results and charges.

## JSearch: candidate vacancies

- Source surface: Google for Jobs/public job-board listings, with employer application links where supplied.
- Route: OpenWeb Ninja JSearch, `GET https://api.openwebninja.com/jsearch/search-v2`, header `x-api-key` from `JSEARCH_API_KEY`.
- [Provider documentation](https://www.openwebninja.com/api/jsearch).
- Parameters: query, country, date window, one page. The adapter expects `status: OK` and `data.jobs`.
- Configured planning rate: $0.005/request, to be checked against the operator's plan. Six default calls yield a $0.03 estimate for this stage only, excluding minimum purchases/taxes.

JSearch is a third-party aggregator, not Google's official Jobs API. Listings may be stale, repeated or missing corporate domains. The workflow does not guess missing domains or take a third-party “direct” flag as ownership proof. Direct employer monitoring is a useful alternative for a known account list and can give stronger provenance; a Google Jobs actor is another discovery route, with different cost and maintenance tradeoffs.

## Optional employer page verification

`checks.verify_employer` defaults to `false`. The listing itself is the hiring signal; careers pages are not fetched and no second description analysis runs. With this optional check enabled, the standard-library HTTP client reads employer pages and supported public Workday detail records. Structured HTML `JobPosting` content is supported, including JSON-LD graphs. Some pages require JavaScript, block retrieval or omit structured fields; these go to review. There is no browser/anti-bot bypass.

For a hosted board, prefer establishing the exact employer route from a corporate link. `checks.trusted_careers` can hold previously reviewed host/path prefixes. Never trust an entire shared hosting service, or add a prefix solely because a syndicated listing supplied it. Workday URLs are converted to the documented public detail path pattern; tenant/site ownership still comes from the employer route.

## OpenAI: read and explain responsibilities

- `POST https://api.openai.com/v1/responses` with `OPENAI_API_KEY` and operator-selected `OPENAI_MODEL`.
- [Structured output documentation](https://developers.openai.com/api/docs/guides/structured-outputs).
- Strict JSON schema, `store: false`, no browsing/tools, source text marked untrusted, limited input characters and output tokens.
- Quotes must occur in the supplied description. Refusal and incomplete output halt the run without retry. Completed answers with invalid schemas or unsupported quotes are quarantined; other records continue.

There can be at most 30 listing analyses by default. Enabling optional employer verification adds at most 10 employer-description analyses. Each includes up to 20,000 source characters plus prompt/metadata; output is capped at 1,500 tokens. Character limits are not precise token or dollar caps. Enter the intended model's current input/output rates in the plan and budget conservatively for all calls, including reasoning/output billing where applicable. No default model or model price is silently assumed. `store: false` is an API storage preference, not a claim about all provider retention policies.

Exact quotation checking guards against fabricated evidence strings. It cannot establish correct interpretation or remove the need to inspect model classifications in a live pilot.

### Existing Azure OpenAI access

`analysis.provider = "azure"` uses `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_BASE_URL` and `AZURE_OPENAI_MODEL`. The base must be an HTTPS Azure OpenAI host ending in `/openai/v1`; requests use the `api-key` header and the same Responses structured-output contract. The local proof selects the already configured `gpt-5.6-luna` deployment with low reasoning effort. This avoids the inherited direct OpenAI key, which returned HTTP 401 during the read-only authentication check. Azure authentication and inference have both been exercised live.

The portable `mvp.toml` and example pilot retain direct OpenAI as their default model route. Set the provider and credentials explicitly for the environment running the proof. Azure billing must be reconciled against its actual rates; the old direct-OpenAI planning rates are not represented as confirmed Azure prices.

## Apify: bounded Meta ad sample (selected route)

- Actor: [`apify/facebook-ads-scraper`](https://apify.com/apify/facebook-ads-scraper), maintained by Apify; reviewed build `0.0.378` is pinned in the TOML files.
- Credential: `APIFY_TOKEN`, sent as a Bearer header only. Never put it in a URL.
- Tested mode: `ad_lookup = "company_search"` uses a Meta Ad Library URL with `search_type=keyword_exact_phrase` and the discovered employer name. It requires an exact normalized advertiser-name match plus consistent numeric page IDs and the matching company destination domain.
- Optional `corporate_page` mode resolves a single Facebook page linked by the account website. Missing or multiple pages go to review without an actor run. `[checks.facebook_pages]` can hold an operator-reviewed mapping, explicitly recorded as supplied input.
- `POST /v2/acts/apify~facebook-ads-scraper/runs` starts one actor per eligible account, with `maxTotalChargeUsd=0.145`, `restartOnError=false` and a 180-second run timeout.
- Input: one page or Meta search URL, `resultsLimit=25`, `activeStatus=active`, and `onlyTotal`, `includeAboutPage`, `isDetailsPerAd`, `enrichWithEcommerceData` all false. This implementation supports all-country page sampling only.
- Persist the returned run ID immediately. Poll that same run at most eight times with `waitForFinish=25`; never restart it after a timeout or failure. Read dataset metadata and at most 25 rows only after `SUCCEEDED`. Incomplete, oversized or error datasets stop the workflow.
- Normalize documented `adArchiveID`/`adArchiveId`, `isActive`, `pageID`/`pageId`, `snapshot.pageProfileUri`, `snapshot.linkUrl` and card `linkUrl` fields. Require consistent numeric page IDs, a matching page profile/ID (page mode) or advertiser name (search mode), and a matching company landing domain. Missing activity is unknown, even though active ads were requested.

**Cost:** the current undiscounted rate is $5.80/1,000 ad records; platform usage is included. The two-account proof requests at most 50 records, with a $0.29 aggregate actor ceiling. The free account's $5 monthly credit is a funding allowance, not the underlying price. No account upgrades or credit purchases are made. The larger ten-account configuration has a $1.45 actor ceiling and is outside the small proof scope.

Returned unique active records and identity/domain-matched records remain separate. A limited dataset is never called complete companywide inventory; total ad count stays unknown. Landing domains and corporate page links are evidence, not proof of spend, performance or purchase intent. A native-library spot-check remains part of live validation. An unresolved vanity/page-ID mapping is not guessed.

Run metadata can report preliminary cost immediately after completion; reconcile it with a later status/account read before claiming final spend.

Sources: [actor input](https://apify.com/apify/facebook-ads-scraper/input-schema), [output](https://apify.com/apify/facebook-ads-scraper/output-schema), [pricing](https://apify.com/apify/facebook-ads-scraper/pricing), [start run](https://docs.apify.com/api/v2/act-runs-post), [read run](https://docs.apify.com/api/v2/actor-run-get), [dataset items](https://docs.apify.com/api/v2/dataset-items-get).

## Optional legacy Adyntel adapter

Setting `checks.ad_provider = "adyntel"` selects the original `POST https://api.adyntel.com/facebook` adapter. It needs `ADYNTEL_API_KEY` and `ADYNTEL_EMAIL`; the Apify route does not. It reads one response page, keeps reported counts separate from returned/domain-matched records, and treats HTTP 204 as unresolved. It has not been live tested. No automatic fallback or purchase is performed. [Documentation](https://docs.adyntel.com/ad-libraries/meta.md).

## Blitz: possible functional owners

- `POST /v2/enrichment/domain-to-linkedin`, followed by `POST /v2/search/employee-finder` on `https://api.blitz-api.ai`.
- Header `x-api-key` from `BLITZ_API_KEY`.
- [Current OpenAPI schema](https://docs.blitz-api.ai/api-reference/v2.openapi.json).
- One employee page, at most 20 returned records/account by default; local ranking retains up to three. Maximum default: 20 calls and 200 employee records.
- The checked paid plan starts at $399/month with fair-use terms. Do not model this as a zero-cost provider or a made-up per-request credit rate. Record actual subscription/incremental purchase costs before a pilot; trial allowances are not the production cost model.

The current schema uses `experiences[]`, including `job_is_current`, `job_end_date`, `company_domain`, title and location. A record is a provider assertion of current employment. A matching title does not prove that person is the hiring manager. The job's geography scopes the search; global owners outside that scope may be missed. No email or phone enrichment endpoints are called.

An employer leadership page or manually verified professional profile is a useful alternative for small named-account samples; it may offer better direct role evidence but less coverage.

## Costs, failures and secrets

`plan` prints call/record caps, configured rates, JSearch estimates and the Apify run ceilings. It does not invent an all-in price when Blitz subscription or model access/rates are missing. Optional OpenAI/Blitz rates are displayed for budgeting, not used to claim a guaranteed total. Minimum purchases, subscriptions, taxes and any charges for failed requests belong in the approval budget.

Before any live acquisition, agree the exact configuration, route, meaningful alternatives, maximum calls/records, monetary ceiling, sample size and pass criteria. Prefer the small [pilot](PILOT.md) before the default run. The package has produced a one-account live research list; it has not sent outreach.

Requests are sequential and never automatically retried. A receipt is written before a paid request. Timeouts, non-object responses, redirects, unexpected schemas and parsing failures halt the run and preserve partial output. A receipt marked `uncertain` may already represent a charged request. Reconcile it with the provider before starting a new run; a new output folder is not a billing-safe resume.

Public fetches reject local/private addresses and credential-bearing URLs, check redirects and cap page size. API credentials go only to fixed provider endpoints; API redirects do not forward credentials. API keys and the Adyntel email are redacted from saved values. Live results still contain private research and contact data: keep the entire run folder private. Do not paste credentials into config, shell arguments, source text, issue reports or output links.


## What the live pilot changed

On 17 September, JSearch and Azure inference ran live. Apify also ran live against the Facebook page linked by Estée Lauder Companies' website; it returned a zero-ad page summary and charged $0.0058 for that row. On 18 September, the fresh production-role query completed with 20 matching active Meta records and 14 employee records returned by Blitz; three contacts were selected.

The actor can emit a summary row with `results: []`, `totalCount: 0`, matching `inputUrl` and `pageInfo.page.id`, a complete-result flag, and an explicit no-CAPTCHA flag. The adapter recognises this as no ads reported for the selected page. It does not infer that related brands have no ads or call the account-wide result complete. Unknown identity or missing flags remain unresolved.

Dataset metadata initially reported zero rows while the items endpoint returned one. The adapter now allows one metadata readback of the same dataset within the existing shared read cap. When metadata still lags bounded observed rows, the discrepancy is retained and the sample remains explicitly incomplete; missing rows or over-limit values still halt. If a readback leaves insufficient capacity to inspect another dataset, another actor cannot start. This is a readback, not an automatic replacement scraping run.

A completed model answer that fails quote validation is quarantined without another model call; unaffected candidates continue. Timeouts and incomplete model responses still halt.

The employer verifier now recognises Eightfold's public careers interface and its `position_details` response. It requires the same public employer domain, exact job ID and matching title plus `positionUserActions.applyAction.status == "allowed"`. This confirms application availability; a generic careers-page shell or a future expiry date alone does not.
