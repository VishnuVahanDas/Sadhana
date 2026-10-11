# Sadhana Report — Update: Chart Scaling & Bhakti Yatra

Oct 11, 2026 · @Vipul

## Context

The Sadhana Report site at sadhna.iskcongorakhpur.com is live with the original specification (SPEC.md v1.0). This update adds two approved changes on top of it:

- **Part A — Chart scaling and festival days:** festival spikes (3–5 hours of seva or reading) no longer squash the normal 0–120 minute days in charts and the heatmap.
- **Part B — Bhakti Yatra:** rounds become a vehicle, daily minutes become Utsāha (enthusiasm), streaks become Dhairya (patience), and the rank table is replaced by a Sanga Yatra page.

If any item in Part A was already built after the 10 Oct 2026 decision, keep it and skip that item.

**Rules for a live site**

- Every change is additive. No existing table, column or entry is deleted or rewritten.
- Totals, averages, streaks and Excel exports keep using real, unclipped values. Only the display changes.
- Migrations are reviewed before they run on the server, and the database is backed up first.
- The main iskcongorakhpur.com site, its Nginx config, services and database are never touched.
- Claude Code asks before running any command on the server.

## Part A — Chart scaling and festival days

Charts open in a "Usual range" view that caps the axis at a typical day, so a 300-minute festival day no longer flattens the rest.

**A1. Capped axis (default view)**

- Axis max = 90th percentile of the period's non-zero daily values × 1.2, rounded up to a clean number (60, 90, 120, 150, 180, 240…).
- Floor: never below 60 for minute fields; for count fields, never below 16.
- Fewer than 7 non-zero days in the period: use the full range.
- Days above the cap are drawn clipped at the top with a marker showing the real value (e.g. "▲ 300"); the tooltip shows the real value.
- Toggle above each chart: **Usual range** (default) / **Full range**.
- Logic in a pure, tested function: `reports/services/scaling.py`.

**A2. Heatmap**

- Colour scale uses the same usual-range cap, not the yearly maximum.
- Days above the cap use the darkest colour; tooltip shows the real value.

**A3. One chart per field**

- Hearing, Reading, Seva, Rounds and any enabled custom numeric field each get their own small chart with its own axis, stacked vertically.

**A4. Typical day and 7-day average**

- Summary cards add **Typical day** (median of daily values in the period) next to Daily average.
- Each trend chart shows daily bars plus a thin 7-day rolling average line.

**A5. Festival days**

- New `FestivalDay` model (name, start\_date, end\_date, notes); a single day has start = end; overlapping ranges allowed.
- Superuser page `/manage/festivals/` to add, edit and delete; every change is audit logged.
- Charts show festival days with a soft gold background band and the festival name on hover.
- Analysis filter: **All days** (default) / **Regular days only** / **Festival days only**. The filter changes totals, averages, typical day and days filled; it never changes streaks.
- When a period contains a festival, Analysis shows a summary, e.g. "Janmashtami — Seva: 1,850 min across 22 devotees".

**Not doing:** log scale, broken axis, automatic exclusion of festival days.

## Part B — Bhakti Yatra

Each devotee travels a Bhakti Yatra: rounds decide the vehicle (Niścaya), daily minutes light the Utsāha meter, and streaks show Dhairya. No km/h or speed numbers appear anywhere.

**B1. Niścaya — My vehicle (from rounds)**

- Based on the **average rounds over the last 7 days, counting filled days only**.
- At least **3 filled days** in the last 7 are needed; before that, show "Starting the journey" with the walking icon.
- Purpose: stability and regularity, not one-day performance. A missed report does not pull the vehicle down; streaks already reward filling every day.
- Vehicle and Utsāha are independent (a devotee on foot can still have a full flame).

| Average rounds (7 days) | Vehicle |
| --- | --- |
| 0–3 | Walking (Padayatra) |
| 4–7 | Cycle |
| 8–11 | Bike |
| 12–15 | Three-wheeler |
| 16–31 | Car |
| 32–47 | Train |
| 48–63 | Airplane |
| 64+ | Vaikuntha Vimāna |

Use simple original icons for each vehicle (no brand imagery); the Vaikuntha Vimāna icon should look celestial (lotus, gold). Walking is framed with dignity: "Padayatra — every step counts".

**B2. Utsāha — today's enthusiasm (from minutes)**

- Utsāha = Hearing + Reading + Seva minutes for the day.
- Shown as a diya meter plus the real minutes, e.g. "Utsāha: three diyas (90 min offered today)".

| Minutes offered today | Meter |
| --- | --- |
| 0 | No lamp yet |
| 1–29 | 1 diya |
| 30–59 | 2 diyas |
| 60–119 | 3 diyas |
| 120+ | Full flame |

- Festival days simply show the full flame, so the meter never breaks.
- For a week, show average minutes per day with the matching meter.

**B3. Dhairya — patience (streaks)**

- Existing streaks are relabelled **Dhairya** in the UI: current, longest and on-time streaks per field.
- Streak logic itself is unchanged.

**B4. Configurable**

- Vehicle thresholds, names and icons, and the Utsāha meter cut-offs are editable by a superuser (see Data model). The tables above are the seed values.

## Sanga Yatra page and the verse

The Sanga Yatra page replaces the Rank table in the menu; it shows the group travelling together, never ordered by score.

**Verse shown at the top of the page — Śrī Upadeśāmṛta, Text 3 (Śrīla Rūpa Gosvāmī)**

> उत्साहान्निश्चयाद्धैर्यात् तत्तत्कर्मप्रवर्तनात् । सङ्गत्यागात्सतो वृत्तेः षड्भिर्भक्तिः प्रसिध्यति ॥
>
> *utsāhān niścayād dhairyāt* *tat-tat-karma-pravartanāt* *saṅga-tyāgāt sato vṛtteḥ* *ṣaḍbhir bhaktiḥ prasidhyati*

Short meaning (our own wording): devotional service becomes successful through six things — enthusiasm, firm confidence, patience, carrying out the prescribed practices, giving up association unfavourable to bhakti, and following the example of saintly devotees. For the full translation, quote Śrīla Prabhupāda's *The Nectar of Instruction* with credit.

| Sanskrit | Meaning | In the app |
| --- | --- | --- |
| utsāha | Enthusiasm | Today's Utsāha meter (minutes offered) |
| niścaya | Firm confidence, steady commitment | My vehicle (7-day rounds) |
| dhairya | Patience | Dhairya streaks |
| tat-tat-karma-pravartana | Carrying out the practices | The daily sadhana entry |
| sato vṛtti | Following saintly devotees | Travelling together on Sanga Yatra |

A small info button beside Utsāha, Niścaya and Dhairya anywhere in the app opens this explanation.

**Page sections**

| Section | Content |
| --- | --- |
| My Journey | My vehicle, today's Utsāha, Dhairya streaks, personal bests (e.g. longest Dhairya, best Utsāha day this month) |
| On the road together | Participating devotees grouped by vehicle, names alphabetical within each group, Dhairya flame beside each name; no ordering by score |
| Sanga offering | "Together today the sanga offered X hours of hearing, reading and seva"; same for this week and this month |

**Rank table**

- Removed from navigation.
- Kept in code behind a new superuser setting `rank_table_enabled`, off by default, for special events such as a Kartik challenge.
- When off, `/ranks/` redirects to the Sanga Yatra page.

**Other places**

- Home (after saving an entry): My vehicle and today's Utsāha.
- My Report and each devotee's page: a Bhakti Yatra card with the same three items.
- Navigation label "Ranks" becomes "Sanga Yatra".

## Data model and settings changes

Three new tables and one new setting; no existing table or column changes.

| Model | Fields | Notes |
| --- | --- | --- |
| `FestivalDay` | name, start\_date, end\_date (≥ start), notes | Part A5; index on start\_date, end\_date |
| `VehicleLevel` | min\_rounds (unique), name, icon (static path), description, order | Part B1; seeded with the 8 vehicles; vehicle = highest level with min\_rounds ≤ 7-day average |
| `UtsahaLevel` | min\_minutes (unique), label, diya\_count, is\_full\_flame | Part B2; seeded with 0 / 1 / 30 / 60 / 120 |
| `AppSettings` (existing) | + `rank_table_enabled` (default False) | New column with a default, safe on a live table |

**Services (pure, unit-tested)**

- `reports/services/scaling.py` — usual-range cap.
- `sadhana/services/yatra.py` — `my_vehicle(user, today)`, `utsaha(minutes)`, `sanga_offering(period)`.
- Vehicle uses rounds from `EntryValue` for the `rounds` field; Utsāha sums the `hearing`, `reading` and `seva` fields.

**Superuser pages**

- `/manage/festivals/` — Festival days.
- `/manage/yatra/` — edit vehicle levels and Utsāha levels.
- `/manage/settings/` — adds the Rank table on/off switch.
- All changes audit logged with new actions: `festival_create`, `festival_update`, `festival_delete`, `yatra_level_update`.

## Rolling out on the live site

Build and test locally, back up the live database, then deploy in two small releases so each can be checked and rolled back on its own.

**Release order**

1. **Release 1 — Part A** (chart scaling, festival days).
2. **Release 2 — Part B** (Bhakti Yatra, Sanga Yatra, rank-table switch).

**Steps for each release**

1. Build and run all tests locally against a copy of the live data (`pg_dump` restored into a local database).
2. Show the migration files and `python manage.py sqlmigrate` output for review before deploying.
3. On the server, back up first: `pg_dump -Fc sadhna_db > ~/backups/sadhna_before_<release>_<date>.dump`.
4. Pull code, install requirements, build Tailwind, `migrate`, `collectstatic`.
5. Restart only the sadhana service: `sudo systemctl restart sadhna` (no Nginx change is needed for this update).
6. Smoke test: log in, save an entry, open My Report, Analysis and Sanga Yatra on a phone; confirm the main iskcongorakhpur.com site still loads.

**Rollback**

- Code: check out the previous release tag and restart the service.
- Database: migrations are additive, so the old code runs with the new tables in place; restore the backup only if data was damaged.

**Timing**

- Deploy at a quiet hour (e.g. 1–3 PM IST), not in the early morning or late evening when devotees fill entries.

## Tests and acceptance checklist

Each release is accepted when its automated tests pass and every item below is checked on a phone.

**Automated tests**

- Cap: 90th percentile × 1.2 with rounding, floor of 60 (minutes) and 16 (count), full-range fallback below 7 days.
- Clipped bars and heatmap cells carry the real value.
- Festival range membership: single day, range, overlap.
- "Regular days only" changes totals and averages but not streaks.
- Excel exports always contain real values.
- My vehicle: 7-day average over filled days only; fewer than 3 filled days gives "Starting the journey"; each threshold boundary (3/4, 15/16, 63/64).
- Utsāha meter at 0, 1, 29, 30, 59, 60, 119, 120 minutes.
- Sanga Yatra excludes inactive devotees and lists names alphabetically within each vehicle.
- `/ranks/` redirects when `rank_table_enabled` is off.

**Release 1 — manual checks**

- [ ] A festival day no longer squashes normal days on My Report
- [ ] Usual range / Full range toggle works
- [ ] Heatmap shows normal days in the full colour range
- [ ] A superuser can add Janmashtami and see the gold band and festival summary

**Release 2 — manual checks**

- [ ] Home shows My vehicle and Utsāha after saving an entry
- [ ] Streaks are labelled Dhairya everywhere
- [ ] Sanga Yatra shows the verse, meaning table and three sections
- [ ] Rank table hidden from the menu; switch in settings brings it back
- [ ] Main iskcongorakhpur.com site unaffected

## Prompt for Claude Code

Export this doc as Markdown, save it as `docs/UPDATE-2026-10-bhakti-yatra.md` in the project, then paste:

```
The Sadhana Report site is live. Read CLAUDE.md, docs/SPEC.md and docs/UPDATE-2026-10-bhakti-yatra.md.

1. Compare the update doc with the current code. Tell me which items in Part A are already built and which are not.
2. List any questions or conflicts with the existing code.
3. Propose the plan for Release 1 (Part A, only the missing items) and Release 2 (Part B): models, migrations, services, templates.
4. Wait for my "go ahead" before writing code.

Rules:
- The site is live. Changes must be additive; never delete or rewrite existing data.
- Show me migrations (with sqlmigrate output) before they run on the server.
- Back up sadhna_db before every deploy.
- Never touch the main iskcongorakhpur.com site.
- Ask before running any command on the server.
```
