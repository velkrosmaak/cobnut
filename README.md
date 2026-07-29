# Chores & Rewards

A small Flask app for tracking kids' chores and reward tokens.

## Features

- Multiple kids, each with their own profile image and their own **token
  icon** (e.g. one kid earns stars, another earns coins — fully configurable
  per kid).
- Each kid has their own chore list. Chores have a name, a token value, a
  **daily** or **weekly** repeat cycle, and a configurable image.
- Kid-facing screen: pick a kid, tap "Mark done" on a chore, tokens are
  added. A chore already completed for the current day/week is greyed out
  until it resets.
- Parent admin area (password protected) to add/edit/delete kids and
  chores, upload images, and log reward redemptions (tokens spent).
- Stats dashboard: tokens earned per kid, completions by hour of day,
  completions by day of week, and most-completed chores — all as
  histograms/bar charts (Chart.js).

## Setup

```bash
cd chores_app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python set_admin_password.py   # prints a line to paste into .env
# edit .env: set SECRET_KEY and paste in ADMIN_PASSWORD_HASH

python app.py
```

Visit `http://localhost:5000/` for the kid picker and
`http://localhost:5000/admin/` for the parent admin area. The browser will
prompt for the username/password you configured (default username is
`admin`).

Until you set `ADMIN_PASSWORD_HASH`, the admin area falls back to
username `admin` / password `admin` — change this before leaving the app
reachable outside your home network.

## Data & images

- SQLite database file `chores.db` is created automatically on first run.
- Uploaded images are stored under `static/uploads/{kids,chores,tokens}/`.
- Nothing here needs a build step — it's a standard Flask + SQLAlchemy app.

## About the "password protected admin page" requirement

You asked for the admin page to be htaccess-protected. Worth knowing: a
plain `.htaccess` file only takes effect when **Apache itself** is directly
serving the filesystem path in question (with `AllowOverride` enabled for
that directory) — e.g. an old-school PHP app. Flask apps are normally run
via gunicorn/uwsgi and reverse-proxied by Apache/Nginx, in which case
`/admin` isn't a real directory on disk and a `.htaccess` file dropped
somewhere won't be consulted at all.

So this app protects `/admin/*` directly in Flask using HTTP Basic Auth
(`utils.admin_required`), which behaves identically to `.htaccess` from the
browser's point of view (a username/password popup) and works no matter how
you deploy it — dev server, gunicorn, behind any proxy.

If you *are* deploying behind Apache and want a second layer of protection
at the web-server level too, see:

- `deploy/apache_reverse_proxy.conf.example` — the correct approach for a
  typical `ProxyPass`-based deployment (a `<Location /admin>` block in the
  vhost, since `.htaccess` doesn't apply to proxied paths).
- `deploy/admin.htaccess.example` — a genuine `.htaccess` file, for the less
  common case where Apache + mod_wsgi serves the app directory directly.

## Notes on chore periods

- **Daily** chores reset at midnight (local server time).
- **Weekly** chores reset at the start of the week (Monday).
- A chore can only be marked done once per period; the button disables
  itself and shows when it resets.

## Ideas for extending later

- PIN per kid instead of a shared picker (kept simple here since it's for
  siblings sharing one household screen).
- Push notifications when a chore streak is broken.
- CSV export of completions from the stats page.
