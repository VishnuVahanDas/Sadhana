# Sadhana Report — Full Specification

**Site:** https://sr.iskcongorakhpur.com
**Owner:** ISKCON Gorakhpur
**Users:** ~20–25 devotees (small, closed group — no public registration)
**Version:** 1.0 (agreed 10 Oct 2026)

---

## 1. Purpose

A private, mobile-first web app where devotees log their daily sadhana (hearing, reading, seva, rounds, etc.), and everyone in the group can view reports, streaks and rank tables — similar in spirit to HackerRank/GitHub streaks, with a devotional look.

---

## 2. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | |
| Framework | Django 5.x | Server-rendered templates |
| Database | PostgreSQL 16 | Separate DB + DB user for this project |
| DB driver | psycopg 3 | |
| UI | Django templates + Tailwind CSS (standalone CLI build, no Node required) | Mobile-first |
| Interactivity | HTMX (small partial updates), minimal vanilla JS / Alpine.js | No SPA |
| Charts | Chart.js | Trend lines / bars |
| Heatmap | Custom server-rendered grid (CSS grid / SVG) | GitHub/HackerRank style |
| Excel export | openpyxl | |
| Config | django-environ (`.env`) | No secrets in git |
| Tests | pytest + pytest-django | |
| App server | gunicorn (systemd service, unix socket) | |
| Web server | Nginx + Certbot (Let's Encrypt) | |
| i18n | Django gettext, English only for now | All user-facing strings wrapped in `gettext` so Hindi can be added later |
| Time zone | `TIME_ZONE = "Asia/Kolkata"`, `USE_TZ = True` | All "today" logic in IST |

---

## 3. Roles & Permissions

There are only **two roles**. "Coordinator" is **not** a role — it is a grouping field.

| Action | User | Superuser |
|---|---|---|
| Log in (email + password) | ✅ | ✅ |
| Fill / edit own sadhana entries | ✅ (subject to settings, §7) | ✅ (never locked) |
| View **everyone's** reports, ranks, notes | ✅ | ✅ |
| View Analysis (`/analysis/`) and its export | ❌ (redirected to Today) | ✅ |
| See streaks | Only in Advanced display mode | Only in Advanced display mode (Analysis always shows them) |
| Switch own display mode (Simple / Advanced) | ✅ | ✅ (and anyone's, single or bulk) |
| Change own password | ✅ | ✅ |
| Export reports / rank tables to Excel | ✅ | ✅ |
| Add / edit users | ❌ | ✅ |
| Reset any user's password | ❌ | ✅ |
| Set a user's coordinator | ❌ | ✅ |
| Mark user inactive / reactivate | ❌ | ✅ |
| Grant / revoke superuser | ❌ | ✅ |
| Enable / disable fields per user | ❌ | ✅ |
| Add / edit / deactivate sadhana fields | ❌ | ✅ |
| Change app settings (edit lock, backfill limit) | ❌ | ✅ |
| Edit any user's entry | ❌ | ✅ (logged in audit) |
| View audit log | ❌ | ✅ |

Rules:
- There can be **multiple superusers**.
- Every superuser is **also a normal user** who fills their own sadhana and appears in analysis/ranks.
- The system must prevent removing superuser status from the **last remaining** superuser.
- **No self-registration**, no "forgot password" email flow. Superusers create accounts and reset passwords.
- Every page except login requires authentication.

---

## 4. Data Model

### 4.1 `User` (custom user model — set up before the first migration)

| Field | Type | Notes |
|---|---|---|
| `email` | EmailField, unique | `USERNAME_FIELD` — used only for login |
| `name` | CharField | Legal / common name |
| `spiritual_name` | CharField, blank | Initiated name, e.g. "Govinda Das" |
| `phone` | CharField, blank | |
| `coordinator` | FK → `User`, null, `on_delete=SET_NULL`, `related_name="team_members"` | Who this devotee comes under |
| `is_coordinator` | Boolean, default False | Only to populate the coordinator dropdown |
| `is_participating` | Boolean, default True | **"Active/Inactive" in the UI.** Inactive users can still log in but are hidden from current rank tables and the group analysis dashboard |
| `is_superuser` | Boolean | App superuser (Django's flag) |
| `is_staff` | Boolean | Mirror `is_superuser` (allows `/admin/` as backup) |
| `is_active` | Boolean | Django's login flag — keep `True`; only for emergency hard-disable |
| `must_change_password` | Boolean, default True | Forces password change on first login and after a reset |
| `date_joined` | DateTime | Used as the start bound for averages |

Property `display_name` → `spiritual_name` if set, else `name`. **Use `display_name` everywhere in the UI.** Email is never shown in lists except on superuser management pages.

### 4.2 `SadhanaField` (configurable fields)

| Field | Type | Notes |
|---|---|---|
| `key` | SlugField, unique | e.g. `hearing` |
| `label` | CharField | e.g. "Hearing" |
| `field_type` | Choice | `minutes`, `count`, `time`, `boolean`, `text` |
| `unit` | CharField, blank | e.g. "min", "rounds" |
| `min_value` / `max_value` | Integer, null | Validation for numeric types (minutes default 0–1440) |
| `has_streak` | Boolean | Whether streaks/streak rankings are computed |
| `is_rankable` | Boolean | Whether it appears in the rank table metric selector (numeric/boolean only) |
| `is_core` | Boolean | Core fields cannot be deleted, only deactivated |
| `is_active` | Boolean | Inactive = hidden from forms everywhere; history kept |
| `enabled_by_default` | Boolean | Default state for users who have no per-user override |
| `order` | Integer | Display order on the form |
| `help_text` | CharField, blank | |

**Seed data (data migration):**

| key | label | type | unit | has_streak | is_rankable | is_core | is_active | enabled_by_default |
|---|---|---|---|---|---|---|---|---|
| `hearing` | Hearing | minutes | min | ✅ | ✅ | ✅ | ✅ | ✅ |
| `reading` | Book Reading | minutes | min | ✅ | ✅ | ✅ | ✅ | ✅ |
| `seva` | Seva | minutes | min | ✅ | ✅ | ✅ | ✅ | ✅ |
| `rounds` | Rounds | count | rounds | ❌ | ✅ | ✅ | ✅ | ✅ |
| `notes` | Notes / Realizations | text | — | ❌ | ❌ | ✅ | ✅ | ✅ |
| `wake_up_time` | Wake-up Time | time | — | ❌ | ❌ | ❌ | ✅ | ❌ |
| `sleep_time` | Sleep Time | time | — | ❌ | ❌ | ❌ | ✅ | ❌ |
| `mangala_arati` | Mangala Arati | boolean | — | ✅ | ✅ | ❌ | ✅ | ❌ |
| `day_rest` | Day Rest | minutes | min | ❌ | ❌ | ❌ | ✅ | ❌ |

(The last four exist but are **off by default**; a superuser switches them on for specific users or for everyone.)

Removing a field: if it has any stored values → deactivate only. If it has no values and is not core → may be hard-deleted.

### 4.3 `UserFieldSetting` (per-user enable/disable)

| Field | Type |
|---|---|
| `user` | FK → User, CASCADE |
| `field` | FK → SadhanaField, CASCADE |
| `enabled` | Boolean |

Constraint: `UniqueConstraint(user, field)`.

**Effective rule:** a field shows on a user's form if `field.is_active` AND (`UserFieldSetting.enabled` if a row exists, else `field.enabled_by_default`). Superuser UI: per-user toggles + a "apply to all users" bulk action per field.

### 4.4 `SadhanaEntry` — one per user per day

| Field | Type | Notes |
|---|---|---|
| `user` | FK → User, CASCADE | |
| `date` | DateField | The **sadhana day**, not the submit time |
| `created_at` | DateTime, auto | Used for "on-time" |
| `updated_at` | DateTime, auto | |
| `created_by` / `updated_by` | FK → User, null | Differ from `user` when a superuser edits |

```python
class Meta:
    constraints = [
        models.UniqueConstraint(fields=["user", "date"], name="one_entry_per_user_per_day"),
    ]
    indexes = [models.Index(fields=["date"]), models.Index(fields=["user", "date"])]
```

Property `is_on_time`: `localdate(created_at) <= date + 1 day` (IST). I.e. entered on the same day or the next day.

### 4.5 `EntryValue` — one value per field per entry

| Field | Type |
|---|---|
| `entry` | FK → SadhanaEntry, CASCADE, `related_name="values"` |
| `field` | FK → SadhanaField, PROTECT |
| `value_int` | PositiveIntegerField, null (minutes, count) |
| `value_time` | TimeField, null |
| `value_bool` | Boolean, null |
| `value_text` | TextField, blank |

Constraint: `UniqueConstraint(entry, field, name="one_value_per_field_per_entry")`.
Helper `value` property returns the typed value based on `field.field_type`.

### 4.6 `AppSettings` (singleton, id=1)

| Field | Default | Meaning |
|---|---|---|
| `edit_lock_enabled` | **False** | If on, normal users cannot edit entries older than `edit_window_days` |
| `edit_window_days` | 7 | |
| `backfill_limit_enabled` | **False** | If on, normal users cannot create entries older than `backfill_limit_days` |
| `backfill_limit_days` | 7 | |
| `day_rollover_hour` | 4 | Before this hour (IST), the entry form defaults to **yesterday** |
| `site_title` | "Sadhana Report" | |

Default = fully open (users can edit or backfill any record). Superusers are never restricted.

### 4.7 `AuditLog` (append-only)

| Field | Type | Notes |
|---|---|---|
| `timestamp` | DateTime, auto | |
| `actor` | FK → User, SET_NULL | Who did it |
| `action` | Choice | `entry_create`, `entry_update`, `entry_delete`, `user_create`, `user_update`, `password_reset`, `user_deactivate`, `user_reactivate`, `superuser_grant`, `superuser_revoke`, `field_create`, `field_update`, `field_toggle_user`, `settings_update` |
| `target_user` | FK → User, SET_NULL, null | Whose data |
| `entry_date` | Date, null | |
| `field_key` | CharField, blank | Store key (string) so logs survive field changes |
| `old_value` / `new_value` | TextField, blank | String representation |
| `ip_address` | GenericIPAddressField, null | |

- Log **one row per changed field value** on entry create/update (not one blob).
- Never edit or delete audit rows from the UI. Admin registers it read-only.

---

## 5. Entry Form Rules

1. **Default date:** today (IST); if current IST hour < `day_rollover_hour`, default to yesterday. User can pick another date.
2. **No future dates.**
3. **Create-or-edit, never duplicate:** opening a date that already has an entry loads it pre-filled; saving updates it. Implement with `transaction.atomic()` + `get_or_create` on `(user, date)`; on `IntegrityError` (race), re-fetch and update. The user never sees a duplicate error.
4. **Only effective fields** (§4.3) are shown. Values for fields later disabled stay in history and still appear in past reports.
5. **Validation:** numeric fields within `min_value`–`max_value`; empty numeric = not entered (store null, treat as 0 for totals, as "not done" for streaks).
6. **Edit lock** (if enabled, non-superusers): reject edits where `date < today - edit_window_days`. Show a friendly message; past entries display read-only.
7. **Backfill limit** (if enabled, non-superusers): reject creating entries where `date < today - backfill_limit_days`.
8. **Superuser editing another user:** via that user's history page → "Edit"; `updated_by` = superuser; audit logged.
9. **Delete entry:** user may delete own entry within the same edit rules; audit logged.
10. After save: success toast + show updated streak badges.

The form must be **fast on mobile** (target: under 30 seconds to fill). Numeric inputs use `inputmode="numeric"`; large tap targets; quick "+15 / +30" chip buttons for minute fields are a nice-to-have.

---

## 6. Streak Engine

Applies only to fields with `has_streak = True` (initially: Hearing, Reading, Seva; Mangala Arati when enabled). **Rounds:** no streak in ranks or analysis, but each devotee's own pages (Today, My Report) show a Rounds streak where any rounds above zero count (see `has_personal_streak`). A threshold may be added later, so keep the engine extensible: `qualifies(value) -> bool` per field, default `value > 0` / `value is True`.

### 6.1 Qualifying day
A day qualifies for a field if an entry exists for that date **and** its value for that field is > 0 (or `True` for boolean). Missing entry or empty/0 value = not qualifying.

### 6.2 Metrics per user per field

| Metric | Definition |
|---|---|
| **Current streak** | Consecutive qualifying days ending **today**. Grace rule: if today has no qualifying value yet, count ending **yesterday** (so the streak doesn't show 0 all morning). |
| **Longest streak** | Longest run of consecutive qualifying days, all time. |
| **On-time current streak** | Same as current streak, but a day only qualifies if the entry `is_on_time`. |
| **On-time longest streak** | Same as longest, on-time days only. |

Both normal and on-time streaks are **displayed side by side** everywhere streaks appear (agreed "Option C").

### 6.3 Implementation notes
- Compute from a single query of `(date, value)` per user/field, ordered by date; walk the list in Python. With 25 users this is trivially fast.
- Put all logic in a pure, unit-tested module: `sadhana/services/streaks.py`.
- Optional: cache per user in Django's cache, invalidated on entry save.

---

## 7. Analysis

### 7.1 Period presets (all views)
Last 7 days · Last 10 days · Last 15 days · Last 30 days · This week · Last week · This month · Last month · Custom range.
**Weeks start on Monday.** Periods include today.

### 7.2 Scopes
- **Individual** — any user (everyone can view everyone).
- **Coordinator group** — a coordinator + their team members.
- **All together** — every participating user.

Inactive (`is_participating=False`) users are **excluded** from group/all aggregates and rank tables, but their own individual page and history remain viewable.

### 7.3 Individual dashboard (`/u/<id>/`)
- Header: display name, coordinator, active badge.
- **Summary cards per rankable field** for the selected period: Total, Daily average, Days filled, and for streak fields: Current streak 🔥, Longest streak, On-time current, On-time longest.
- **Trend chart** (Chart.js): daily values per field over the period (toggle fields).
- **Calendar heatmap** (last 365 days, GitHub/HackerRank style) with a field selector; colour intensity by value; tooltip with date and value.
- **Entries table** for the period: date, each field value, notes, on-time indicator. Owner/superuser see Edit links.
- Excel export of the entries table.

### 7.4 Group / All dashboard (`/analysis/`)
Filters: period, scope (All / coordinator), field.
- **Totals AND average per person, side by side** (agreed):
  - Total = sum over participating users.
  - Average per person = total ÷ number of participating users in scope.
  - Also show average per person per day.
- **Community trend chart:** daily total and daily average per person.
- **Per-user table:** display name, coordinator, total, daily avg, days filled, current streak, on-time streak. Sortable columns.
- **"Not filled today"** list (participating users with no entry for today).
- Excel export of the per-user table.

### 7.5 Daily average definition
`total ÷ number of calendar days in the period`, where the period start is bounded by the user's `date_joined` (so new users aren't penalised). Days filled = count of entries in the period.

---

## 8. Rank Table (`/ranks/`)

> Since the October 2026 update (docs/UPDATE-2026-10-bhakti-yatra.md) the rank table is off by default: Sanga Yatra (`/yatra/`) takes its place in the navigation, and `/ranks/` redirects there unless a superuser switches on `rank_table_enabled` in Settings.

Selectors:
- **Metric (field):** any `is_rankable` field (Hearing, Reading, Seva, Rounds, + any enabled custom numeric/boolean).
- **Rank by** — all of these are available (agreed "show all"):

| Rank by | Period filter applies? | Available for |
|---|---|---|
| Current streak | No (live) | Streak fields only |
| Longest streak | No (all-time) | Streak fields only |
| On-time current streak | No | Streak fields only |
| On-time longest streak | No | Streak fields only |
| Total | Yes | All rankable |
| Daily average | Yes | All rankable |
| Days filled | Yes | All rankable |

- Streak options are hidden/disabled when the metric has no streak (e.g. Rounds).
- **Period** selector (same presets as §7.1) for Total/Average/Days filled.
- **Coordinator filter:** All, or one coordinator's team.
- **Ties:** competition ranking (1, 1, 3).
- Top 3 get 🥇🥈🥉 styling; show the logged-in user's own row highlighted.
- Only participating users.
- Excel export.
- Mobile: card list; desktop: table.

---

## 9. Screens & URLs

| URL | Who | Purpose |
|---|---|---|
| `/login/` | Public | Email + password |
| `/logout/` | All | |
| `/password/change/` | All | Forced when `must_change_password` |
| `/` | All | **Home:** today's entry form (or yesterday before rollover) + my streak badges + quick links |
| `/entry/<yyyy-mm-dd>/` | Owner (+superuser via `?user=<id>`) | Create/edit entry for a date |
| `/me/` | All | Redirect to own individual dashboard |
| `/devotees/` | All | Directory of all users (search, filter by coordinator, active/inactive) |
| `/u/<id>/` | All | Individual dashboard (§7.3) |
| `/analysis/` | Superuser | Group/All dashboard (§7.4); others are redirected to Today |
| `/mode/` | All | POST: switch own display mode (docs/UPDATE-2026-10-simple-advanced-mode.md) |
| `/ranks/` | All | Rank table (§8); redirects to `/yatra/` unless `rank_table_enabled` is on |
| `/yatra/` | All | Sanga Yatra: verse, My Journey, On the road together, Sanga offering |
| `/manage/festivals/` | Superuser | Festival days |
| `/manage/yatra/` | Superuser | Vehicle levels and Utsāha levels |
| `/export/...` | All | Excel downloads for the above |
| `/manage/users/` | Superuser | List, add, edit, reset password, set coordinator, mark coordinator, active/inactive, superuser toggle |
| `/manage/users/<id>/fields/` | Superuser | Per-user field toggles |
| `/manage/fields/` | Superuser | Add/edit/reorder/deactivate fields; "enable for all users" bulk action |
| `/manage/settings/` | Superuser | AppSettings form (§4.6) |
| `/manage/audit/` | Superuser | Filterable audit log (by user, action, date) |
| `/admin/` | Superuser | Django admin as a backup tool |

Navigation (mobile bottom bar): **Today · My Report · Sanga Yatra · Analysis (superusers only) · More** (More → Devotees, Change password, Manage* for superusers, Logout).

**Password reset by superuser:** superuser sets a temporary password (or clicks "generate"), shown once on screen to share with the devotee; `must_change_password=True`.

---

## 10. Look & Feel

- **Devotional, clean, mobile-first.**
- Palette (Tailwind theme tokens):
  - Saffron `#E8751A` (primary actions)
  - Maroon `#7A1F2B` (headers, nav)
  - Gold `#C9A227` (highlights, medals, streak flames)
  - Cream `#FFF8EE` (background)
  - Ink `#2B2118` (text)
- Fonts: **Noto Sans** (body) + **Noto Serif** (headings) via Google Fonts — both have Devanagari variants for future Hindi.
- Temple logo at `static/img/logo.png` (placeholder until supplied) on login page and header.
- Login page: logo, "Hare Krishna 🙏" greeting, subtle lotus/mandala motif.
- Heatmap colour scale: cream → light saffron → saffron → maroon.
- Accessible contrast; tap targets ≥ 44px.

---

## 11. Security

- `DEBUG=False` in production; secrets in `.env`.
- `ALLOWED_HOSTS = ["sr.iskcongorakhpur.com"]`, `CSRF_TRUSTED_ORIGINS` set.
- `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_PROXY_SSL_HEADER`, HSTS.
- Login rate limiting (e.g. `django-axes` or simple cache-based throttle: 5 failures / 15 min).
- Long session (e.g. 30 days, "remember me" by default) — devotees fill daily from phones.
- All views `login_required`; manage views `superuser_required`.
- Django password validators on.

---

## 12. Project Structure (suggested)

```
sadhna/
├── manage.py
├── .env.example
├── requirements.txt
├── config/                 # settings, urls, wsgi
├── accounts/               # custom User, auth views, user management
├── sadhana/                # fields, entries, values, settings, entry form
│   └── services/
│       ├── streaks.py      # pure streak logic
│       ├── analytics.py    # totals, averages, period helpers
│       ├── ranking.py
│       └── periods.py      # preset → (start, end) in IST, Monday weeks
├── audit/                  # AuditLog + helpers
├── reports/                # dashboards, ranks, excel exports
├── templates/
├── static/  (src css, built css, js, img/logo.png)
├── deploy/                 # nginx conf, systemd unit, backup script
└── tests/
```

---

## 13. Tests (minimum)

- DB constraint: second entry for same user/date raises `IntegrityError`; form path updates instead.
- Day rollover default date at 03:59 vs 04:00 IST.
- Edit lock and backfill limit: on/off, superuser exemption.
- Streaks: gaps, zero values, grace rule for today, on-time vs backfilled entries, longest streak.
- Period presets: Monday week start, month boundaries.
- Averages: bounded by `date_joined`; per-person average excludes inactive users.
- Ranking: ties (1,1,3), streak options hidden for Rounds.
- Last-superuser protection.
- Audit rows created per changed field.

---

## 14. Deployment (same VPS as iskcongorakhpur.com — must not disturb it)

**Golden rule:** the existing iskcongorakhpur.com site and its payment gateway must not be touched. Only **add** new files; never edit the existing site's Nginx config, systemd units, venv, or database.

1. **DNS:** `A` record `sadhna` → server IP.
2. **Code:** `/var/www/sadhna/` (own directory), own Python venv.
3. **Database:** new Postgres DB `sadhna_db` and role `sadhna_user` (no access to other DBs).
4. **Env:** `/var/www/sadhna/.env` (chmod 600).
5. **Build:** `pip install -r requirements.txt`, Tailwind build, `migrate`, `collectstatic`, create first superuser (`createsuperuser` by email).
6. **gunicorn:** `deploy/sadhna.service` → `/etc/systemd/system/sadhna.service`, unix socket `/run/sadhna/gunicorn.sock`, 2–3 workers.
7. **Nginx:** new file `deploy/nginx-sadhna.conf` → `/etc/nginx/sites-available/sr.iskcongorakhpur.com` + symlink. Serves `/static/` directly. Run `sudo nginx -t` **before** reload.
8. **TLS:** `sudo certbot --nginx -d sr.iskcongorakhpur.com` (only this domain).
9. **Backups:** `deploy/backup.sh` — nightly `pg_dump` of `sadhna_db` via cron, keep 14 days.
10. **Smoke test:** main site still loads and payments page still works; then the new subdomain.

---

## 15. Build Phases (review after each)

| Phase | Scope | Done when |
|---|---|---|
| 1 | Project skeleton, settings, custom User, login/logout/password change, base layout + theme | Can log in on mobile with themed UI |
| 2 | SadhanaField + seed migration, UserFieldSetting, SadhanaEntry, EntryValue, AppSettings, entry form with all rules, AuditLog | Can fill/edit today and past entries; audit rows written |
| 3 | Manage pages: users, per-user fields, fields, settings, audit viewer | Superuser can run the system without `/admin/` |
| 4 | Services (periods, streaks, analytics) with tests; individual dashboard with cards, chart, heatmap | Personal report complete |
| 5 | Group/All analysis, rank table, Excel exports | All views complete |
| 6 | Polish, security settings, full test pass, deploy files, deployment | Live on sr.iskcongorakhpur.com |

---

## 16. Later (not in v1)

- Hindi translation.
- Rounds streak with a threshold (e.g. 16 rounds) and per-user targets.
- Daily reminder (WhatsApp/Telegram/push) for those who haven't filled.
- PWA install (manifest + service worker).
- Weekly summary message.
