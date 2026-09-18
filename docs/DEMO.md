# Two-minute demonstration

Open [the saved report](../examples/demo/report.md), or run:

```bash
python3 -m creative_signal demo --output runs/demo
```

Start by saying: **“These are fictional records. This demonstrates the process; the next step is to test the same process on a small live sample.”** The offline run makes no network calls and uses canned model outputs as well as synthetic job, ad and people responses. Normal adapters, listing-evidence validation, filters, ranking and exports still run.

1. **Show the input and decisions.** Eight vacancy records entered. One was a duplicate; one was product design; one account was excluded; one lacked a domain. One listing was stale. Three accounts reached advertising research.
2. **Open Demo Harbour Brands.** Its job listing assigns brand standards and channel specifications for paid social, across markets and agencies. The brief retains the exact quotes and stated reporting role.
3. **Show the ads.** The Apify fixture passes through the real adapter. The sample contains three unique active records, and two have landing URLs matching the account domain. Total inventory stays unknown. The workflow exposes the returned and matched counts separately, and retains the simulated run/dataset receipts.
4. **Show the people.** A possible current creative-operations director is included. A former employee and someone at another company are discarded. The person's actual remit still needs confirmation.
5. **Show the approach.** Investigate whether supported digital-asset checks could help this team's stated responsibilities. That is a specific conversation direction, not an assertion of broken processes or buying intent.
6. **Open the unresolved/closed cases.** The stale listing receives no ad/contact enrichment. An unresolved ad lookup stays unknown and does not produce a claim of zero ads.

The concrete ambition is: a rep opens a useful account brief instead of rebuilding these joins and checks across several tabs. The live pilot must establish accuracy, yield and actual time saved before that benefit is claimed.

The current demo uses job listings directly. Employer website verification is disabled, and there is no second model call per account.
