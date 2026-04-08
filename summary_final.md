# Summary Final

## Output Files

- Master CSV: `master_merged_agents_contacts.csv`
- Mine source: `Find_all_boutique_placement_agents_capital_results_2026-03-26T13-43-51_decision_makers.csv`
- Other source: `Identify_Boutique_Capital_Placement_Agents-d6079c21-b822-4a70-be09-5fdc0b28313d-results.csv`

## Merge Rules

- Shared/original columns were kept once.
- Columns unique to my enrichment were added with a `mine_` prefix.
- Columns unique to the other agent enrichment were added with an `other_` prefix.
- No derived confidence or scoring columns were added to the master CSV.

## Overall Findings

- Both files align on `84` shared firm rows.
- My file reports `decision_maker_contact_found` on `35` firms, `generic_email_only` on `25`, `names_only` on `1`, and `no_public_contact_found` on `23`.
- My file includes personal decision-maker emails on `6` firms and decision-maker LinkedIn URLs on `34` firms.
- My file includes multiple decision-maker contacts on `33` firms.
- The other file populated non-placeholder `decision_maker_email` on `82` rows and non-placeholder `decision_maker_linkedin` on `83` rows.
- In the other file, `81` email values match a normal email pattern and `82` LinkedIn values are personal-profile URLs.
- The other file stores generic inboxes as `decision_maker_email` on at least `18` rows.
- Exact agreement is limited: `13` firms share at least one identical email or LinkedIn URL across both files.
- `22` firms have contact data in both files but point to different people or different direct contacts.
- The other file adds some contact where my file had none on `49` firms.
- Of those additions, `35` look like person-specific emails and `11` are generic inboxes.

## Quality Notes On Other File

- `other_basis.decision_maker_email.citations` is empty or `[]` on `84` of `84` rows.
- `other_basis.decision_maker_linkedin.citations` is empty or `[]` on `84` of `84` rows.
- The other reasoning mentions `ContactOut` on `6` rows.
- The other reasoning mentions inferred email patterns or similar inference language on `15` rows.
- The other reasoning mentions company-page based identification on `9` rows.
- I found `1` malformed multi-firm row where one record contains a bullet list for many firms.

## Agreement Examples

- `Black Isle Capital Partners`: other email `steve.holt@blackislecp.com`, other LinkedIn `https://uk.linkedin.com/in/stephen-holt-1605875` overlaps with at least one value in my file.
- `Stonington Capital Advisors`: other email `info@stoningtoncapital.com`, other LinkedIn `https://www.linkedin.com/in/dana-pawlicki-9466956` overlaps with at least one value in my file.
- `FIRSTavenue`: other email `pbuckley@firstavenue.com`, other LinkedIn `https://uk.linkedin.com/in/paul-derek-buckley-2999291` overlaps with at least one value in my file.
- `Touchstone Group, LLC`: other email `tcunningham@touchstonegroupllc.com`, other LinkedIn `https://www.linkedin.com/in/timothy-cunningham-14097/` overlaps with at least one value in my file.
- `New Harbor Venture Partners`: other email `mbosland@newharborvp.com`, other LinkedIn `https://www.linkedin.com/in/markbosland` overlaps with at least one value in my file.
- `Troy Investment Advisors`: other email `suzanne@troyinv.com`, other LinkedIn `https://www.linkedin.com/in/suzannetroycole` overlaps with at least one value in my file.
- `MCAM Group`: other email `info@mcamgroup.com`, other LinkedIn `https://uk.linkedin.com/in/bjoergerd` overlaps with at least one value in my file.
- `FirstPoint Equity`: other email `justin@firstpointequity.com`, other LinkedIn `https://uk.linkedin.com/in/justinrbower` overlaps with at least one value in my file.

## Useful Additions From Other File

These are firms where the other file has a contact while my file had no decision-maker contact at all.

- `The Beck Group Ltd`: other email `m.beck@the-beck-group.com`, other LinkedIn `https://uk.linkedin.com/in/madeleine-beck-wagner-676a21175`.
- `KPG Capital Partners`: other email `kgettinger@kpgcapitalpartners.com`, other LinkedIn `https://www.linkedin.com/in/kennethgettinger`.
- `Capital Investment Marketing, Inc.`: other email `tim.stoddart@cap-invest-marketing.com`, other LinkedIn `https://www.linkedin.com/in/timstoddart`.
- `Sophic Capital Inc.`: other email `sean@sophiccapital.com`, other LinkedIn `https://ca.linkedin.com/in/seanpeasgood`.
- `Raisman Investor Relations & Consulting`: other email `pavel@raisman.uk`, other LinkedIn `https://www.linkedin.com/in/pvdmitriev`.
- `Frontier Business Advisory Limited`: other email `priesnell@frontierbusiness.org`, other LinkedIn `https://www.linkedin.com/in/priesnell/`.
- `Brand Iron`: other email `mdoyle@brandiron.net`, other LinkedIn `https://www.linkedin.com/in/brandiron`.
- `CrossBay Capital Partners`: other email `jsindelar@crossbaycapital.com`, other LinkedIn `https://www.linkedin.com/in/joseph-sindelar-jr-82308410`.
- `Aditum Group`: other email `contact@aditumgroup.com`, other LinkedIn `https://www.linkedin.com/in/bob-reese-760a992/`.
- `Hall & Evans, LLC`: other email `Not publicly available.`, other LinkedIn `https://www.linkedin.com/in/tom-beam-618519217`.
- `Worthwhile Capital Partners`: other email `christian.andersson@worthwhilecap.com`, other LinkedIn `https://se.linkedin.com/in/christian-andersson-7755111`.
- `Worldview Capital Inc`: other email `Joe@worldview.capital`, other LinkedIn `https://www.linkedin.com/in/joezcunningham/`.

## Richer Coverage In My File

These are examples where my file captured multiple senior contacts rather than a single contact.

- `Black Isle Capital Partners`: `3` contacts captured. Sample: `Steve Holt | Founder & Managing Partner | steve.holt@blackislecp.com | https://uk.linkedin.com/in/stephen-holt-1605875 | Robbie Bowker | Managing Partner | robbie.bowker@blackislecp.com | https://uk.linkedin.com/in/robbie-b-633625196 | Peter Brackett | Partner | peter.brackett@blackislecp.com | https://uk.linkedin.com/in/peter-brackett-01b8086`.
- `Stonington Capital Advisors`: `3` contacts captured. Sample: `Dana C. Pawlicki | Managing Partner | https://www.linkedin.com/in/dana-pawlicki-9466956 | Dan Rudgers | Senior Managing Director | https://www.linkedin.com/in/dan-rudgers-b431128 | Patrick O’Meara | Senior Adviser | https://www.linkedin.com/in/patrickdomeara`.
- `Jemini Capital`: `3` contacts captured. Sample: `Matt Salthouse | CEO | https://www.linkedin.com/in/matt-keis-0427156 | Terry Filbert | CEO | https://www.linkedin.com/in/terry-gilbert-28781324 | Tony Guo | CEO | https://www.linkedin.com/pub/dir/tony/guo`.
- `Capitalaxōn`: `3` contacts captured. Sample: `John Muirhead | Managing Partner | https://www.linkedin.com/in/john-muirhead | Adam Gross | Managing Director | https://www.linkedin.com/in/adam-m-gross | Maurizio Caroglio | Managing Director | https://www.linkedin.com/in/maurizio-caroglio-a05a5227`.
- `FIRSTavenue`: `3` contacts captured. Sample: `Paul Buckley | Managing Partner | pbuckley@firstavenue.com | Stephen Suk-Hyun Shin | Managing Director | Andrew Rosato | Partner`.
- `Touchstone Group, LLC`: `3` contacts captured. Sample: `Timothy Cunningham | President | tcunningham@touchstonegroupllc.com | https://www.linkedin.com/in/timothy-cunningham-14097 | Michael Wagner | Managing Director | mwagner@touchstonegroupllc.com | https://www.linkedin.com/in/michael-wagner-4958578 | Merlin Schulze | Senior Advisor | mschulze@touchstonegroupllc.com | https://www.linkedin.com/in/ericschulze`.
- `New Harbor Venture Partners`: `2` contacts captured. Sample: `Mark Bosland | Founder | mbosland@newharborvp.com | http://www.linkedin.com/pub/mark-bosland/1/aa4/468 | Jake Hindelong | Managing Director | jhindelong@newharborvp.com | https://www.linkedin.com/in/jakehindelong`.
- `Acuity Advisors`: `2` contacts captured. Sample: `David Burdette | Managing Director | https://www.linkedin.com/in/david-burdette-8b150a4 | Jill Moro | Director`.

## Notable Discrepancies

- `Jemini Capital`: mine email(s) `<none>`, mine LinkedIn(s) `https://www.linkedin.com/in/matt-keis-0427156; https://www.linkedin.com/in/terry-gilbert-28781324; https://www.linkedin.com/pub/dir/tony/guo`; other email `kevin@jeminicapital.com`, other LinkedIn `https://ca.linkedin.com/in/kevineshum`.
- `Capitalaxōn`: mine email(s) `<none>`, mine LinkedIn(s) `https://www.linkedin.com/in/adam-m-gross; https://www.linkedin.com/in/john-muirhead; https://www.linkedin.com/in/maurizio-caroglio-a05a5227`; other email `capital@capitalaxon.com`, other LinkedIn `https://www.linkedin.com/in/carlafavila/`.
- `Acuity Advisors`: mine email(s) `<none>`, mine LinkedIn(s) `https://www.linkedin.com/in/david-burdette-8b150a4`; other email `r.baker@acuity.co.uk`, other LinkedIn `https://www.linkedin.com/in/richardabaker/`.
- `Thrive Alternatives`: mine email(s) `<none>`, mine LinkedIn(s) `https://fr.linkedin.com/in/ye-wang-103843114/en; https://hk.linkedin.com/in/elizabeth-oh-5b605421; https://hk.linkedin.com/in/mai-takeuchi-73b7a6a2`; other email `info@thrivealts.com`, other LinkedIn `https://linkedin.com/in/jackson-chan-425a2123`.
- `Crito Capital`: mine email(s) `<none>`, mine LinkedIn(s) `https://www.linkedin.com/in/ileana-boza-a499ab55; https://www.linkedin.com/in/matthew-r-wagner-05b3154; https://www.linkedin.com/in/sarah-killick-19181410`; other email `ted.gillman@critocapital.com`, other LinkedIn `https://www.linkedin.com/in/critocapital`.
- `Selinus Capital GmbH`: mine email(s) `<none>`, mine LinkedIn(s) `https://de.linkedin.com/in/andrea-lehmann-gutermuth-04628311`; other email `kulke@selinus-capital.com`, other LinkedIn `https://de.linkedin.com/in/mathias-kulke-50264a84`.
- `Atlantic‑Pacific Capital`: mine email(s) `<none>`, mine LinkedIn(s) `https://www.linkedin.com/in/martin-phillips-8319447`; other email `relkhatib@apcap.com`, other LinkedIn `https://www.linkedin.com/in/raed-elkhatib-a4a1381/`.
- `Mvision`: mine email(s) `<none>`, mine LinkedIn(s) `https://fi.linkedin.com/in/saadullahakram`; other email `mg@mvision.com`, other LinkedIn `https://www.linkedin.com/in/mounir-moose-guen-3636937`.
- `Probitas Partners`: mine email(s) `<none>`, mine LinkedIn(s) `https://www.linkedin.com/in/carynpfeinberg; https://www.linkedin.com/in/joe-maertens-cfa-caia-a4408425; https://www.linkedin.com/in/ray-tsao`; other email `parsram.dhanraj@probitaspartners.com`, other LinkedIn `https://www.linkedin.com/in/parsram-dhanraj-77973322/`.
- `Langschiff Capital Partners`: mine email(s) `<none>`, mine LinkedIn(s) `https://www.linkedin.com/in/anna-gordon-098588196; https://www.linkedin.com/in/tamara-fears-29770517`; other email `info@langschiff.com`, other LinkedIn `https://www.linkedin.com/in/nolanolsen`.

## Data-Quality Issues To Review

- `Stonington Capital Advisors`: generic inbox stored as decision_maker_email: info@stoningtoncapital.com.
- `Capitalaxōn`: generic inbox stored as decision_maker_email: capital@capitalaxon.com.
- `Aditum Group`: generic inbox stored as decision_maker_email: contact@aditumgroup.com.
- `Thrive Alternatives`: generic inbox stored as decision_maker_email: info@thrivealts.com.
- `MCAM Group`: generic inbox stored as decision_maker_email: info@mcamgroup.com.
- `Praxess`: generic inbox stored as decision_maker_email: info@praxess.com.
- `Blue Titan Capital`: generic inbox stored as decision_maker_email: info@bluetitancapital.com.
- `Absolute Global Partners LLC`: generic inbox stored as decision_maker_email: info@absolute-gp.com.
- `PIEXTON CAPITAL`: generic inbox stored as decision_maker_email: info@piexton-capital.com.
- `Langschiff Capital Partners`: generic inbox stored as decision_maker_email: info@langschiff.com.
- `Threadmark LLP; Denning & Company, LLC; Acanthus Advisers LLP; Axonia Partners GmbH; Probitas Partners; Triago; Setter Capital Inc.; Monument Group, Inc.; Atlantic-Pacific Capital, Inc.; FocusPoint Private Capital Group; Stanwich Advisors, LLC; FIRSTavenue Partners LLP`: multi-firm list stored in one row.

## Recommended Use

- Use the master CSV as the working table because it preserves both sources without collapsing disagreements.
- When both sources disagree, review the `mine_*` and `other_*` fields side by side before outreach.
- Pay extra attention to other-agent rows whose reasoning mentions `ContactOut`, `RocketReach`, or inferred email formats, since those are less strictly verified than direct firm-page contacts.
