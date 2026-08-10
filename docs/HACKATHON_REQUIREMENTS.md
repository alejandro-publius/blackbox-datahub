# Hackathon Requirements (verified 2026-08-09)

**Hackathon:** "Build with DataHub: The Agent Hackathon" (Online, Public — datahub.devpost.com)
**Sources verified today via live fetch:** main page (https://datahub.devpost.com/), rules (https://datahub.devpost.com/rules), resources (https://datahub.devpost.com/resources), announcement blog (https://datahub.com/blog/build-with-datahub-agent-hackathon/). All four pages were reachable.
**Prize pool:** $20,500 total. ~2,969 participants registered. Hackathon manager contact: lakshay@datahub.com.

> Sourcing note: Devpost pages were extracted via a fetch tool that limits long verbatim quotation. Category names, criterion titles, and short quoted phrases below are verbatim as returned from the live pages; longer descriptions are close paraphrases of the official text and are marked as such where relevant.

---

## Deadline & timeline (exact dates/times/timezones)

| Phase | Start | End |
|---|---|---|
| Registration & Submission Period | July 6, 2026, 9:00 AM ET | **August 10, 2026, 5:00 PM ET (EDT)** |
| Feedback Period (for Feedback Prize) | July 6, 2026, 9:00 AM ET | August 10, 2026, 5:00 PM ET |
| Judging Period | August 17, 2026, 10:00 AM ET | August 31, 2026, 5:00 PM ET |
| Winners Announced | On or around September 8, 2026, 2:00 PM ET | — |

**URGENT: As of the verification date (2026-08-09), the submission deadline is TOMORROW — August 10, 2026 at 5:00 PM EDT.**

---

## Eligibility & registration requirements

**Open to:**
- Individuals age 18+ (or above the legal age of majority in their country/jurisdiction of residence).
- Teams of eligible individuals.
- Organizations (corporations, nonprofits, LLCs, partnerships, other legal entities).

**NOT eligible:**
- Residents of Brazil, Quebec, Russia, Crimea, Cuba, Iran, North Korea, and other OFAC-designated/US-embargoed territories (standard Devpost exclusions).
- Employees, representatives, and agents of the promotion entities (Sponsor/Administrator) and their immediate family or household members.
- Judges and the companies/organizations they are employed by.
- Parent companies, subsidiaries, or affiliates of ineligible organizations.
- Anyone whose participation creates a real or apparent conflict of interest (Sponsor's discretion).

**Registration:** Register at datahub.devpost.com and create/log into a Devpost account. A team must designate a Representative who is an eligible individual authorized to act on behalf of the team/organization.

**Ineligible projects:** Projects developed with financial or preferential support from the Sponsor/Administrator (funded development, contract development, or commercial licenses received before the end of the Submission Period) are not eligible.

**Multiple submissions:** Allowed, but per the rules: "each Submission must be unique and substantially different from each of the Entrant's other Submissions, as determined by the Sponsor and Devpost in their sole discretion."

---

## Mandatory submission requirements

**What to build (verbatim from rules):** "Entrants must create a working software application that uses DataHub to solve one of the Challenge Categories below. Projects must incorporate DataHub by using the open-source platform together with at least one of: the MCP Server, Agent Context Kit, DataHub Skills, or Analytics Agent."

**New-work requirement (verbatim):** "Projects must be newly created during the Submission Period. Participants may use standard development tools, including frameworks, libraries, starter templates, and AI coding assistants, but must disclose any other pre-existing code or work incorporated into the Project."

**Each submission must include:**

1. **Working project + access for judges** (verbatim): "Access must be provided to an Entrant's working Project for judging and testing by providing a link to a website, functioning demo, or a test build. If Entrant's website is private, Entrant must include login credentials in its testing instructions." A functional URL for testing is required (live demo, hosted app, or a public repository with setup instructions that judges can follow).
2. **Public code repository with Apache 2.0 open-source license.** The rules specify a **public repo with an "Apache 2.0 open source license file"** — visible in the repository (per the extracted rules text, visible in the repo's About/license area). This is a specific license requirement, not "any OSI license."
3. **Text description** summarizing the project's features, functionality, and technologies used.
4. **Demonstration video:**
   - Duration: "less than three (3) minutes" (i.e., strictly under 3:00).
   - Must show the project functioning (a functioning demo of the actual project, on the platform it runs on).
   - Must be uploaded and publicly visible on **YouTube, Vimeo, or Youku**, with the link provided on the submission form.
   - Must not include "third party trademarks, or copyrighted music or other material unless the Entrant has permission" (or the material is otherwise legally usable).
5. **Sample outputs (recommended/optional):** an `examples/` folder showing generated artifacts — explicitly called out for the Metadata-Aware Code Generation category ("Submissions should include sample outputs in an `examples/` folder").
6. **Language:** All submission materials must be in English or include English translations.
7. **Team info:** Team Representative must be an eligible individual authorized to act on behalf of the team/organization. Team members should be added on Devpost.
8. **Originality/IP:** Submission must be the entrant's original work, solely owned by the entrant, and must not violate the IP rights (copyright, trademark, patent, contract, privacy) of any other party.
9. Complete **all required fields** on the Devpost submission page before the Submission Period ends.

---

## Challenge categories / prize tracks

Four challenge categories (names verbatim from the official rules/site). Each category has one $3,000 Challenge Winner; the Grand Prize is drawn from all eligible submissions.

1. **"Agents That Do Real Work"** ← *this is one of our two target categories.*
   Build AI agents that handle data problems autonomously — agents that "read DataHub to understand what's connected to what, take action, and write results back" (blog wording). Examples given: handling dropped columns, governance flags, cascading pipeline impacts. Uses DataHub's MCP Server or Agent Context Kit.

2. **"Metadata-Aware Code Generation & Development"** ← *this is our other target category.* (Note: the Devpost main page shortens this to "Metadata-Aware Code Generation"; the official rules use the full name with "& Development".)
   Blog wording: "Build agents that generate production data code — transformation models, pipeline DAGs, ingestion scripts — that work on the first try because they read DataHub for real schemas, lineage, and rules." Uses DataHub Skills and/or MCP Server to read schemas, lineage, and rules before generating artifacts. Sample outputs in an `examples/` folder are explicitly expected.

3. **"Production ML Agents"**
   Build agents for ML teams that protect models in production using DataHub's end-to-end ML lineage — agents that "catch silent problems, like target leakage, upstream data changes that should have triggered a retrain, or schema drift affecting model quality" (blog wording).

4. **"Open / Wildcard"**
   Blog wording: "If your idea doesn't fit the categories above, build it anyway. Supply chain, financial forecasting, regulatory automation, knowledge capture." Creative uses of DataHub's stack in any domain.

**Prizes:**

| Prize | Amount | Winners | Extras |
|---|---|---|---|
| Grand Prize | $6,000 cash | 1 | Presentation at DataHub Town Hall, social media promotion, special LinkedIn Badge |
| Challenge Winner | $3,000 cash | 4 (one per category) | Social media promotion, LinkedIn Badge |
| Honourable Mention | $1,000 cash | 2 | LinkedIn Badge |
| Most Valuable Feedback Survey | $50 cash | 10 | For complete, actionable feedback submitted via the online form during the Feedback Period (one per entrant) |

- Each submission is eligible for a maximum of one prize.
- Each individual is eligible for a maximum of one Feedback Prize; feedback-only participants are ineligible for project prizes.
- Winners must return Required Forms (identity verification affidavits; W-9 for US residents / W-8BEN for non-US) within ten (10) business days; prizes delivered within 60 days of completed forms.

---

## Judging criteria (two-stage process)

**Stage One — pass/fail viability check (verbatim):** Projects must demonstrate "a baseline level of viability, in that the Project reasonably fits the theme and reasonably applies the required APIs/SDKs." Submissions that fail Stage One are not evaluated further.

**Stage Two — equally weighted criteria** (titles verbatim; descriptions are close paraphrases with short verbatim fragments from the rules page):

1. **Use of DataHub** — "How meaningfully does the project use DataHub — its context graph (lineage, ownership, schemas, ML metadata, governance signals)" — via the MCP Server, Agent Context Kit, DataHub Skills, or Analytics Agent; preference for submissions that also **contribute back to / write to the context graph**.
2. **Technical Execution** — "Quality of implementation, robustness, and whether the project actually works end-to-end."
3. **Originality** — "How creative and novel is the approach? Submissions should clearly go beyond features DataHub already provides" (do not recreate shipped DataHub functionality).
4. **Real-World Usefulness** — "Would a real data, ML, or AI platform team see clear value in this?" Production-readiness is not required, but practitioners should see clear practical value.
5. **Submission Quality** — "Quality of the demo video, written description, and README. A judge should be able to understand what the project does" and be able to follow the setup instructions.
6. **Bonus** — "Submissions that include meaningful open-source contributions to DataHub — new connectors, skills, fixes, RFCs, or documentation improvements" are looked upon favorably.

**Tie-breaking:** Tied submissions are compared on the first applicable criterion sequentially; if still tied, judges vote.

**Feedback Prize criteria (verbatim fragment):** "Evaluated based on the completeness, viability, and potential impact of the feedback" (on DataHub SDKs or documentation).

**Judges:** Tim Bossenmaier (Cloudflight), Aman Gairola (Pinterest), Maggie Hays (DataHub), Alyssa Lee (DataHub), Nick Adams (DataHub), Wenjia You (OpenAI), Mike Burke (Senior Developer).

---

## Required/featured APIs & SDKs (what counts as "using DataHub")

**Hard requirement (rules, verbatim):** the project must use "the open-source platform together with at least one of: the MCP Server, Agent Context Kit, DataHub Skills, or Analytics Agent."

- **DataHub MCP Server** — https://github.com/acryldata/mcp-server-datahub — lets agents/MCP clients query the DataHub context graph.
- **Agent Context Kit** — https://docs.datahub.com/docs/dev-guides/agent-context/agent-context — programmatic agent access to DataHub context.
- **DataHub Skills** — https://docs.datahub.com/docs/dev-guides/agent-context/skills — skills registry; repo: https://github.com/datahub-project/datahub-skills.
- **Analytics Agent** — https://docs.datahub.com/docs/features/feature-guides/analytics-agent — open-source text-to-SQL reference implementation.
- **Context graph** — lineage, ownership, schemas, ML metadata, governance signals; the "Use of DataHub" criterion explicitly rewards reading from AND writing back to the graph.
- The blog also lists "APIs/SDK/CLI" as core access methods and native LLM-framework support (LangChain, LangGraph, Google ADK, any MCP-compatible client). **Ambiguity note:** the binding rules text requires at least one of the four named tools above; plain API/SDK/CLI usage alone may not satisfy the letter of the rules — use the MCP Server or Agent Context Kit to be safe.
- **Setup:** DataHub Quickstart — `pip install acryl-datahub` then `datahub docker quickstart` (https://docs.datahub.com/docs/quickstart).

---

## Bonus criteria (things judges favor)

- **Open-source contributions to DataHub** (explicit Bonus criterion): "new connectors, skills, fixes, RFCs, or documentation improvements."
- **Writing results back to the context graph** (not just reading it) — called out in the Use of DataHub criterion and the "Agents That Do Real Work" category description ("take action, and write results back").
- **Sample outputs in an `examples/` folder** — recommended generally; explicitly expected for the code-generation category.
- **Going beyond shipped DataHub features** (Originality criterion).
- Separate from project judging: the **Feedback survey** ($50 x 10) rewards complete, actionable feedback submitted via the online form during the Feedback Period — one per entrant; does not affect project scoring.

---

## Disqualification risks

Anything on this list can fail Stage One, zero out a criterion, or trigger formal disqualification:

1. **Missing/late submission fields** — all required Devpost fields must be complete before Aug 10, 2026, 5:00 PM EDT. No late submissions.
2. **Video violations** — video 3:00 or longer ("less than three (3) minutes" is the rule), not publicly visible, not on YouTube/Vimeo/Youku, not showing the project actually functioning, or containing third-party trademarks / copyrighted music / other material without permission.
3. **Repository violations** — repo not public, or missing the **Apache 2.0 license file** (the rules name Apache 2.0 specifically, and it should be visible/detected in the repo's About section).
4. **Project not testable by judges** — no working URL/demo/test build; if anything is private/gated, login credentials MUST be in the testing instructions.
5. **Failing Stage One viability** — project doesn't reasonably fit the theme or doesn't reasonably apply the required APIs/SDKs (must genuinely use DataHub OSS + MCP Server / Agent Context Kit / Skills / Analytics Agent).
6. **Not newly created during the Submission Period** — pre-existing projects are ineligible; any incorporated pre-existing code beyond standard dev tools must be disclosed.
7. **IP violations** — work not original/solely owned, or violating "copyright, trademark, patent, contract, and/or privacy rights."
8. **Eligibility violations** — ineligible country, affiliation with sponsor/judges, or conflicts of interest.
9. **Conduct** — tampering with the entry process, violating the Official Rules, unsportsmanlike behavior, or violating applicable law.
10. **Winner verification failures** — not returning Required Forms (affidavits, W-9/W-8BEN) within 10 business days can forfeit a prize.
11. **Materials not in English** (or lacking English translations).
12. *(Practical, implied by public-repo + IP rules)* Do not commit secrets/API keys to the public repo, and disclose all third-party code.

---

## Sample datasets / provided resources

**Documentation:**
- DataHub Docs: https://docs.datahub.com
- Quickstart Guide: https://docs.datahub.com/docs/quickstart (`pip install acryl-datahub` → `datahub docker quickstart`)
- DataHub Skills: https://docs.datahub.com/docs/dev-guides/agent-context/skills
- Agent Context Kit: https://docs.datahub.com/docs/dev-guides/agent-context/agent-context
- DataHub MCP Server: https://github.com/acryldata/mcp-server-datahub
- Analytics Agent: https://docs.datahub.com/docs/features/feature-guides/analytics-agent

**Open-source repos:** DataHub Core (https://github.com/datahub-project/datahub), DataHub Skills (https://github.com/datahub-project/datahub-skills).

**Sample datasets (datapacks):**
- `showcase-ecommerce` — 1,049 entities across multiple platforms
- `bootstrap` — lightweight starter with datasets, dashboards, users, tags
- `nyc-taxi` — NYC Yellow Taxi Trip Records (~500k trips) with pipeline staging
- `healthcare` — synthetic patient records (~55k) with quality issues
- `fiction-retail` — synthetic retail dataset (50k customers, 150k orders)

**Community support:**
- DataHub Slack, **#agent-hackathon** channel: https://join.slack.com/t/datahubspace/shared_invite/zt-3rxzw3uww-7F2k5mDpjKXIGLskiQPwLQ
- DataHub Town Halls: https://datahub.com/community/datahub-town-halls/
- Devpost support: support@devpost.com
- (No office-hours schedule was listed on the fetched pages; the Slack channel is the stated support path throughout the event.)

---

## Exact submission checklist (Devpost, before Aug 10, 2026 @ 5:00 PM EDT)

- [ ] Registered on datahub.devpost.com with a Devpost account; all team members added; eligible Team Representative designated.
- [ ] Project newly created during the Submission Period (Jul 6 – Aug 10, 2026); any incorporated pre-existing code disclosed.
- [ ] Project uses open-source DataHub **plus at least one of**: MCP Server, Agent Context Kit, DataHub Skills, Analytics Agent — and the usage is meaningful (reads the context graph; ideally writes back).
- [ ] Project clearly targets a challenge category (ours: "Agents That Do Real Work" and/or "Metadata-Aware Code Generation & Development"); category selected on the form if asked.
- [ ] **Public GitHub repo** with:
  - [ ] **Apache 2.0 LICENSE file** (shows in the repo About section).
  - [ ] README with clear description + complete setup/testing instructions a judge can follow.
  - [ ] `examples/` folder with sample outputs (strongly recommended; expected for code-gen category).
  - [ ] No secrets/keys committed; third-party code disclosed and license-compatible.
- [ ] **Working project URL** for judges: live demo, hosted app, or test build. If anything requires login, include credentials in the testing instructions.
- [ ] **Demo video**: under 3 minutes; shows the project actually functioning end-to-end; uploaded to YouTube/Vimeo/Youku as **public**; no unlicensed third-party trademarks/music/content; link pasted into the submission form.
- [ ] **Text description** on Devpost covering features, functionality, and technologies used.
- [ ] All materials in English (or with English translations).
- [ ] All required Devpost form fields completed and the submission actually submitted (not left in draft) before **5:00 PM EDT, Aug 10, 2026**.
- [ ] Optional: feedback survey submitted via the online form before the same deadline (one per person; $50 x 10 Feedback Prizes).
- [ ] Optional but judge-favored: open a DataHub OSS contribution (connector, skill, fix, RFC, or docs PR) and link it in the submission.

---

## Ambiguities & open questions

- **Category name variance:** rules say "Metadata-Aware Code Generation & Development"; the Devpost gallery/main page and the blog shorten it to "Metadata-Aware Code Generation". Treat the rules version as authoritative.
- **"APIs/SDK/CLI" in the blog** vs the rules' explicit "at least one of: the MCP Server, Agent Context Kit, DataHub Skills, or Analytics Agent" — build against one of the four named tools to be unambiguous.
- **License wording:** the rules extraction specifies an Apache 2.0 license file "visible in the About section" — GitHub auto-detects standard LICENSE files; use the stock Apache 2.0 text so detection works.
- **Verbatim caveat:** long rule passages above are near-verbatim extractions (fetch tooling limits full-length quotation); criterion titles, category names, and quoted fragments are verbatim. If any single sentence becomes load-bearing for a dispute, re-check https://datahub.devpost.com/rules directly.
