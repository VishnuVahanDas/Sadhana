# Sadhana Report

Private sadhana log for ISKCON Gorakhpur (`sr.iskcongorakhpur.com`). The specification is in `docs/SPEC.md`.

## Setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env          # then set SECRET_KEY and DATABASE_URL
chmod 600 .env
```

Tailwind uses the standalone CLI (v3.4, no Node). Download it once into the project root:

```bash
curl -sSL -o tailwindcss https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64
chmod +x tailwindcss
```

## Commands

```bash
./tailwindcss -i static/src/input.css -o static/css/app.css --minify   # add --watch while developing
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser      # asks for email and name
.venv/bin/python manage.py runserver
.venv/bin/pytest
```

The tests create and drop their own database (`test_<name>`), so the database role needs `CREATEDB`.

## Demo data

```bash
.venv/bin/python manage.py seed_demo            # dev1..dev15 with about 60 days of entries
.venv/bin/python manage.py seed_demo --delete   # remove them again
```

## Deployment

See `deploy/DEPLOY.md`. The deploy files only add a new Nginx site, systemd unit and cron job; they never edit another site.
