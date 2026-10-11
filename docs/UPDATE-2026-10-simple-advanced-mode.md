# Update: Simple / Advanced Mode + Analysis for Superusers Only

**Site:** https://sr.iskcongorakhpur.com (live)
**Date approved:** 11 Oct 2026
**Build order:** This update first. The Bhakti Yatra update (`UPDATE-2026-10-bhakti-yatra.md`) comes after it.

---

## 1. Why

Devotees said the app shows too many things. Most devotees only need to fill their entry and see simple graphs.

## 2. Summary of changes

| # | Change |
|---|---|
| 1 | The **Analysis** tab and `/analysis/` become **superuser only** |
| 2 | New per-user **display mode**: **Simple** (default) or **Advanced** |
| 3 | The **only** difference between the modes: **streak elements are hidden in Simple mode** |
| 4 | A superuser sets each user's mode (single and bulk). A devotee can also switch their own mode in More → Settings |
| 5 | All existing users are set to **Simple** at migration; a superuser moves interested devotees to Advanced |

Everything else stays as it is.

---

## 3. What each mode shows

| Element | Simple | Advanced |
|---|---|---|
| Today tab: entry form | ✅ | ✅ |
| Today tab: streak badges | ❌ | ✅ |
| My Report: summary cards (total, daily average, typical day, days filled) | ✅ | ✅ |
| My Report: streak cards (current, longest, on-time current, on-time longest) | ❌ | ✅ |
| My Report: trend graphs (usual range, full-range toggle, 7-day average line, festival bands) | ✅ | ✅ |
| My Report: heatmap | ✅ | ✅ |
| Excel download | ✅ | ✅ |
| Devotees directory and other devotees' pages | ✅ | ✅ |
| Analysis tab | ❌ (superuser only) | ❌ (superuser only) |
| Manage pages | ❌ (superuser only) | ❌ (superuser only) |

Rules:
- The mode applies to **what the viewer sees**, on their own pages and on other devotees' pages. A Simple-mode user opening another devotee's page sees no streaks there either.
- **Superusers follow their own mode setting** like everyone else. Analysis and Manage are always available to superusers regardless of mode.
- Streak columns in Analysis and in rank/streak tables remain visible to superusers (Analysis is superuser-only).
- Excel exports for a Simple-mode user leave out streak columns; for Advanced users and superusers they include them.

---

## 4. Data model

| Model | Change | Notes |
|---|---|---|
| `User` | Add `ui_mode` CharField, choices `simple` / `advanced`, default `simple` | One migration: add the column with default `simple`, so all existing users become Simple |

No other model changes. No data is deleted.

Helper: `user.is_advanced` property → `ui_mode == "advanced"`.
Template context processor: expose `show_streaks` (= `request.user.is_advanced`) to all templates.

---

## 5. Permissions

- `/analysis/` and every Analysis export URL: superuser only. A normal user who opens the URL is redirected to the Today tab with a friendly message (no error page).
- The **Analysis** item is removed from the navigation for normal users.
- Hiding streaks must happen **in the view/template logic**, not only with CSS. Streak values must not be computed or sent for Simple-mode viewers.

---

## 6. Screens

### 6.1 Navigation
| Viewer | Bottom bar |
|---|---|
| Normal user (either mode) | Today · My Report · More |
| Superuser | Today · My Report · Analysis · More |

(If the rank table setting from the original spec is on, its link still appears as before. The Bhakti Yatra update will later replace it with Sanga Yatra.)

### 6.2 More → Settings (all users)
- New **Display mode** switch: Simple / Advanced, with one line of help text:
  - Simple: "Your entry, graphs and Excel — a clean view."
  - Advanced: "Also shows streaks on Today and My Report."
- Saving it is audit logged (`ui_mode_change`, actor = the user).

### 6.3 Manage → Users (superuser)
- New **Mode** column (Simple / Advanced) in the user list.
- Mode field on the user edit form.
- **Bulk action:** select users → "Set to Simple" / "Set to Advanced".
- Filter the list by mode.
- All changes audit logged (`ui_mode_change`, actor = the superuser, old/new value).

---

## 7. Audit log

Add action `ui_mode_change` to `AuditLog.action` choices. One row per user changed (bulk changes write one row per user).

---

## 8. Effect on the Bhakti Yatra update (for later)

When Bhakti Yatra is built after this update:

| Bhakti Yatra element | Simple | Advanced |
|---|---|---|
| My vehicle (Niścaya) | ✅ | ✅ |
| Utsāha diya meter | ✅ | ✅ |
| Dhairya (streaks) | ❌ | ✅ |
| Sanga Yatra page | Decide after launch and devotee feedback | ✅ |

---

## 9. Tests

- Migration: existing users end up with `ui_mode = "simple"`.
- New users default to Simple.
- Normal user → `/analysis/` redirects to Today; superuser → 200.
- Analysis link absent from navigation for normal users, present for superusers.
- Simple-mode viewer: no streak elements on Today, My Report and other devotees' pages; streak service not called.
- Advanced-mode viewer: streak elements present.
- Superuser in Simple mode: no streaks on Today/My Report, but Analysis still available.
- User can switch own mode in Settings; superuser can switch single and bulk.
- Excel export: streak columns absent for Simple, present for Advanced and superusers.
- Audit rows written for every mode change.

---

## 10. Manual checks after deploy

- [ ] A normal devotee in Simple mode sees: entry form, graphs, heatmap, Excel. No streaks, no Analysis tab.
- [ ] Switching to Advanced in Settings shows streaks on Today and My Report.
- [ ] A superuser sees the Analysis tab and can bulk-change modes.
- [ ] Typing `/analysis/` as a normal user redirects to Today.
- [ ] The main iskcongorakhpur.com site is unaffected.

---

## 11. Deployment (live site)

1. Build and test locally against a copy of live data.
2. Show the migration and `sqlmigrate` output for review.
3. Back up first: `pg_dump -Fc sadhna_db > ~/backups/sadhna_before_ui_mode_<date>.dump`
4. Pull, install requirements, build Tailwind, `migrate`, `collectstatic`.
5. `sudo systemctl restart sadhna` (no Nginx change).
6. Run the manual checks above.
7. Tell devotees in the group: "The app is now simpler. If you'd like streaks back, switch to Advanced in More → Settings."

Rollback: previous release tag + restart. The new column is additive, so the old code runs fine with it.
