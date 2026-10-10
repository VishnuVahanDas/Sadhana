# Deploying Sadhana Report to sadhna.iskcongorakhpur.com

This server also runs the live **iskcongorakhpur.com** site and its payment
gateway. Every step below only **adds** new files. Nothing here edits another
site's Nginx config, systemd unit, virtualenv, database or files.

The layout follows what the other sites on this server already use: code under
`/home/vishnuvahan/`, running as `vishnuvahan:www-data`.

| What | Where |
|---|---|
| Code | `/home/vishnuvahan/sadhana` |
| Virtualenv | `/home/vishnuvahan/sadhana/.venv` |
| Environment | `/home/vishnuvahan/sadhana/.env` (mode 600) |
| Database | `sadhna_db` (PostgreSQL 16) |
| Socket | `/run/sadhna/gunicorn.sock` |
| systemd unit | `/etc/systemd/system/sadhna.service` |
| Nginx site | `/etc/nginx/sites-available/sadhna.iskcongorakhpur.com` |
| Backups | `/home/vishnuvahan/backups/sadhna/` |

## 0. Before you start

1. **DNS:** add an `A` record `sadhna` → `88.222.241.219` and wait until
   `dig +short sadhna.iskcongorakhpur.com` prints that address. Certbot fails without it.
2. **Remove the demo users** if they should not be on the live site:
   `.venv/bin/python manage.py seed_demo --delete`
3. Note that the main site works right now (home page and donation page), so you can compare afterwards.

## 1. Production settings

Edit `/home/vishnuvahan/sadhana/.env`:

```
DEBUG=False
ALLOWED_HOSTS=sadhna.iskcongorakhpur.com
CSRF_TRUSTED_ORIGINS=https://sadhna.iskcongorakhpur.com
```

Keep `SECRET_KEY` and `DATABASE_URL` as they are. With `DEBUG=False` the app
turns on secure cookies, the HTTPS redirect and HSTS by itself.

Stop any `runserver` that is still running: with `DEBUG=False` the site only works over HTTPS.

## 2. Build

```bash
cd /home/vishnuvahan/sadhana
.venv/bin/pip install -r requirements.txt
./tailwindcss -i static/src/input.css -o static/css/app.css --minify
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check --deploy
```

## 3. File ownership

The service runs as `vishnuvahan`, so it must be able to read the project and `.env`:

```bash
sudo chown -R vishnuvahan:www-data /home/vishnuvahan/sadhana
chmod 600 /home/vishnuvahan/sadhana/.env
```

## 4. gunicorn (new systemd unit)

```bash
sudo cp deploy/sadhna.service /etc/systemd/system/sadhna.service
sudo systemctl daemon-reload
sudo systemctl enable --now sadhna
systemctl status sadhna --no-pager
curl --unix-socket /run/sadhna/gunicorn.sock -H "Host: sadhna.iskcongorakhpur.com" -H "X-Forwarded-Proto: https" -sI http://localhost/login/ | head -n 1
```

The last command should print `HTTP/1.1 200 OK`.

## 5. Nginx (new site file)

```bash
sudo cp deploy/nginx-sadhna.conf /etc/nginx/sites-available/sadhna.iskcongorakhpur.com
sudo ln -s /etc/nginx/sites-available/sadhna.iskcongorakhpur.com /etc/nginx/sites-enabled/
sudo nginx -t          # must say "syntax is ok" and "test is successful"
sudo systemctl reload nginx
```

If `nginx -t` fails, **do not reload**. Remove the symlink
(`sudo rm /etc/nginx/sites-enabled/sadhna.iskcongorakhpur.com`) and run `sudo nginx -t` again.

## 6. HTTPS certificate

```bash
sudo certbot --nginx -d sadhna.iskcongorakhpur.com
sudo nginx -t
```

Name only this one domain. Choose "redirect" if Certbot asks.

## 7. Backups

```bash
crontab -e      # as user vishnuvahan, add:
30 2 * * * /home/vishnuvahan/sadhana/deploy/backup.sh >> /home/vishnuvahan/backups/sadhna/backup.log 2>&1
```

Run it once by hand first: `mkdir -p /home/vishnuvahan/backups/sadhna && deploy/backup.sh`.
To restore: `gunzip -c <file>.sql.gz | psql "<DATABASE_URL>"` into an empty database.

## 8. Smoke test

1. https://iskcongorakhpur.com loads, and its donation/payment page still works.
2. https://sadhna.iskcongorakhpur.com shows the login page with a valid certificate.
3. Log in, save an entry, open My Report, Analysis and Ranks, download one Excel file.
4. `journalctl -u sadhna -n 50 --no-pager` shows no errors.

## Updating later

```bash
cd /home/vishnuvahan/sadhana
git pull                               # or copy the new code in
.venv/bin/pip install -r requirements.txt
./tailwindcss -i static/src/input.css -o static/css/app.css --minify
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart sadhna
```

## Rolling back

This removes the new site and leaves everything else as it was:

```bash
sudo rm /etc/nginx/sites-enabled/sadhna.iskcongorakhpur.com
sudo nginx -t && sudo systemctl reload nginx
sudo systemctl disable --now sadhna
```
