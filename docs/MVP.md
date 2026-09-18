# What this first version proves

The manual job is: find a promising company, read its hiring context, check that it advertises, identify a plausible owner, and prepare a defensible account brief. The intended benefit is less research per useful SDR conversation. Time saved and pipeline impact have not yet been measured.

## Why CreativeX

CreativeX's [Creative Quality product](https://www.creativex.com/products/creative-quality) describes defined creative checks, custom guidelines and reporting across markets, brands, agencies and channels. A vacancy explicitly assigning advertising standards or creative-effectiveness work can reveal a relevant team and responsibility. Visible advertising gives another reason to investigate that team.

Hiring for “creative” alone is weak evidence. The useful finding is closer to: “This team owns brand standards and channel requirements across several markets, and we found active advertising linked to its domain.” The sales hypothesis is whether CreativeX's supported checks or measurement layer could help that work. It is not evidence that the current process is broken, that software is absent, or that new budget exists.

Creative judgment, physical product design, legal claims and rights clearance are outside the product claim made by this workflow. A single ad count is not a measure of spend or a diagnosis of creative quality.

The responsibility-led approach was informed by `blueprint-gtm-017`, [Turn a million job posts into buying signals](https://edge.blueprintgtm.com/p/turn-a-million-job-posts-into-buying). The specific workflow, gates and score below are proposed implementation choices, not validated campaign outcomes from that article.

## Inputs and decisions

1. **Discover.** Three configurable query seeds: creative operations, creative production and creative effectiveness. Search a chosen geography and recent posting window. One page per query/country in this release.
2. **Join and filter.** Require a corporate domain. Deduplicate by job ID, application URL or exact employer/title/location combination. Apply named-account inclusion and exclusions before paid description analysis. Parent/brand consolidation requires explicit reviewed aliases.
3. **Read.** Use structured model output to separate advertising governance, creative measurement and unrelated work. Preserve exact excerpts; reject quotations not present in the source. Truncated or incomplete analyses cannot qualify.
4. **Use the listing.** The discovered job description, date and source URL are sufficient hiring evidence. Reuse the listing analysis for the brief; do not fetch or re-analyse an employer careers page in the default workflow.
5. **Check timing and scope.** Require relevant own-brand advertiser responsibilities, coordination scope and a recent listing date. Missing or stale dates are reported. Application availability and employer-site verification are not default requirements.
6. **Check advertising.** Resolve one Facebook page from the corporate website, or a recorded operator-reviewed mapping. Use Apify to sample up to 25 active ads with a $0.145 run ceiling. Require returned advertiser-page identity and a landing URL matching the corporate domain or a reviewed alias. Deduplicate active ad IDs; keep unmatched ads out of the matched count. The sample does not establish total inventory. Missing links or an unresolved vanity/page-ID relationship may cause false negatives; do not repair those joins by guessing.
7. **Find people.** Resolve the corporate domain to a company LinkedIn URL and request one bounded employee page. Require current employment, no end date, matching company domain and relevant title. Rank governance owners for governance signals and measurement owners for measurement signals, with a modest location and reporting-title boost. Return up to three people.
8. **Prepare the brief.** Show observed evidence, interpretation, target role, possible people, suggested conversation direction, sources and missing checks. The human verifies remit and CRM eligibility before deciding what to do.

## Outcomes

| Outcome | Meaning |
|---|---|
| `priority_review` | Listing evidence, freshness, advertising evidence and at least one possible owner passed |
| `needs_review` | A material fact, source or contact remains uncertain; blanks remain unknown |
| `rejected` | The role is unrelated, belongs to an excluded organization type, or is closed/stale |
| `excluded` | Outside the supplied named accounts or on an operator exclusion list |
| `duplicate` | The vacancy was already represented in this run |
| `capped` | Not processed because a job/account limit or one-vacancy-per-account limit applied |

Scoring is used for queue order after gates: retained hiring source +2; relevant exact responsibilities +2; coordination scope +1; recent listing date +1; matched active Meta evidence +1; possible owner +1. Ad volume does not add points. A rejected account can have a few evidence points; status always takes precedence over score.

One strongest candidate per account is researched. Optional `checks.verify_employer = true` enables the extra employer-page check and re-analysis, including application availability; it is disabled in all supplied configurations. Deduplication is within a run, not across a recurring monitor. These are explicit simplicity limits, not evidence that the account has no other relevant roles.

## What a rep sees

- **Observed:** the listing's exact responsibility and scope quotes, role/location, posting and check dates, and bounded advertising records.
- **Potential relevance:** how supported CreativeX checks or creative measurement might relate to that work.
- **Who:** the reporting role from the vacancy where present, plus separately sourced possible owners.
- **Approach:** begin with the verified responsibility and ask about its operation; do not claim pain or quote unverified spend.
- **Before contact:** confirm account/customer status, territory, existing opportunity and the person's current remit.

## Ambition after the pilot

A scheduled process could monitor CreativeX's agreed accounts, detect new or changed evidence, suppress customers and active opportunities using their records, and place a concise research brief in the SDR's existing queue. Human feedback would refine qualification and owner selection. Build that after a small live test demonstrates useful yield and less manual effort; daily scheduling alone does not prove SDR value.
