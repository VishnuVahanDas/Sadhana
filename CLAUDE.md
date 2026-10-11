# CLAUDE.md — Sadhana Report

Project brief for Claude Code. The full, authoritative specification is in **`docs/SPEC.md`** — read it before writing code, and follow it. If something in the spec seems wrong or ambiguous, ask instead of guessing.

## What this is
A private, mobile-first Django web app for ISKCON Gorakhpur where ~20–25 devotees log daily sadhana (hearing, reading, seva, rounds, notes + configurable fields) and view reports, streaks and rank tables. Domain: `sr.iskcongorakhpur.com`.

## Non-negotiables
- **Stack:** Python 3.12, Django 5.x, PostgreSQL (psycopg 3), server-rendered templates, Tailwind (standalone CLI), HTMX, Chart.js, openpyxl. No SPA, no React.
- **Custom User model with email login** must exist before the first migration.
- **Two roles only:** superuser and user. "Coordinator" is a FK field on User, not a role. Multiple superusers allowed; superusers are also normal users. Never allow removing the last superuser.
- **Everyone can view everyone's reports** (including notes). **Analysis (`/analysis/` and its export) is superuser only**; a normal user is redirected to Today with a message.
- **Display mode** (docs/UPDATE-2026-10-simple-advanced-mode.md): `User.ui_mode` is `simple` (default) or `advanced`. Simple hides streaks, for the reader, on every page, and also the per-field summary cards on My Report (asked for by the temple on 11 Oct 2026, after the update doc). Streaks must not be computed for a Simple reader (pass `show_streaks=request.user.is_advanced` down from the view; templates also get `show_streaks`). Superusers follow their own mode; Analysis always keeps its streak columns. No self-registration. No email password reset — superusers reset passwords.
- **"Inactive" = `is_participating=False`**: can still log in, hidden from rank tables and group analysis. Do NOT use Django's `is_active` for this.
- **One entry per user per day**, enforced by a DB `UniqueConstraint(user, date)`; one value per field per entry likewise. Entry form is create-or-update, never a duplicate error.
- **Configurable fields** (`SadhanaField`) with types `minutes`, `count`, `time`, `boolean`, `text`, plus per-user enable/disable (`UserFieldSetting`). Seed data per SPEC §4.2.
- **Edit lock / backfill limit** are settings toggles, **off by default**; superusers are never restricted.
- **Audit log**: one row per changed field value; append-only.
- **Streaks**: Hearing, Reading, Seva (and Mangala Arati when enabled). Rounds has a streak on a devotee's own pages only (Today, My Report; any rounds count), never in ranks or analysis. Show both normal and on-time streaks. Logic lives in pure, unit-tested functions in `sadhana/services/streaks.py`.
- **Bhakti Yatra** (docs/UPDATE-2026-10-bhakti-yatra.md): rounds give the vehicle (Niścaya), minutes the Utsāha meter, and streaks are labelled Dhairya in the UI. Logic in `sadhana/services/yatra.py`; levels are editable at `/manage/yatra/`. The Sanga Yatra page (`/yatra/`) replaces Ranks in the navigation and never orders devotees by score. The rank table stays in the code behind `AppSettings.rank_table_enabled` (off by default); when off, `/ranks/` redirects to `/yatra/`.
- **WhatsApp button** (11 Oct 2026): "Send to coordinator on WhatsApp" is a plain `wa.me` link, shown on the devotee's own Today and My Report in both display modes; the server never sends anything. Hidden when there is no coordinator, the coordinator has no valid phone, the devotee is their own coordinator, or `User.show_whatsapp_button` is off (More sheet, default on). The message never includes streaks, Utsāha or Yatra levels. Logic in `sadhana/services/whatsapp.py`; phones are normalised to `91XXXXXXXXXX` on save in Manage → Users (`accounts/phones.py`) and never rewritten by a migration.
- **Time:** all "today" logic in `Asia/Kolkata`; weeks start Monday; day rollover hour 4 AM.
- **Display names:** always `display_name` (spiritual name, else name). Email is login-only.
- **i18n-ready:** wrap all user-facing strings in `gettext`/`{% translate %}`; English only for now.
- **Theme:** saffron `#E8751A`, maroon `#7A1F2B`, gold `#C9A227`, cream `#FFF8EE`, ink `#2B2118`; Noto Sans/Noto Serif. Mobile-first, tap targets ≥ 44px.

## Server safety (critical)
This app will share a VPS with the live **iskcongorakhpur.com** Django site, which has a working payment gateway. Never modify that site's Nginx config, systemd units, venv, database, or files. Only add new, separate files for this project. Always run `sudo nginx -t` before any reload. Ask before running any command on the server.

## Working style
- Build in the phases in SPEC §15. Stop at the end of each phase, summarise what was built and how to test it, and wait for approval before the next phase.
- Write tests for services and constraints (SPEC §13) as you go; keep them passing.
- Keep secrets in `.env` (provide `.env.example`). Never commit secrets.
- Prefer simple, readable Django over clever abstractions — this is a 25-user app.
- Use migrations for seed data (fields, AppSettings singleton).

## Commands (fill in as the project takes shape)
- Run dev server: `.venv/bin/python manage.py runserver`
- Tests: `.venv/bin/pytest`
- Tailwind build: `./tailwindcss -i static/src/input.css -o static/css/app.css --minify`
