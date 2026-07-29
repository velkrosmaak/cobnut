# Jobs & Rewards

A small Flask app for tracking kids' jobs and reward tokens.

## Features

- Multiple kids, each with their own profile image and their own **token
  icon** (e.g. one kid earns stars, another earns coins — fully configurable
  per kid).
- Each kid has their own job list. Jobs have a name, a token value, a
  **daily** or **weekly** repeat cycle, and a configurable image.
- Kid-facing screen: pick a kid, tap "Mark done" on a job, tokens are
  added. A job already completed for the current day/week is greyed out
  until it resets.
- Parent admin area (password protected) to add/edit/delete kids and
  jobs, upload images, and log reward redemptions (tokens spent).
- Stats dashboard: tokens earned per kid, completions by hour of day,
  completions by day of week, and most-completed jobs — all as
  histograms/bar charts (Chart.js).

## Setup

```bash
cd jobs_app
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

- SQLite database file `jobs.db` is created automatically on first run.
- **Uploaded images (kid profile photos, kid token icons, job images) are
  stored as binary data directly inside `jobs.db`**, not as separate files
  on disk. This means there's only one thing to keep persistent — the
  database file — and images can't quietly go missing on their own.

  (Earlier versions of this app saved images to `static/uploads/...` on
  disk. If you're upgrading from that version, the app automatically adds
  the new database columns it needs the first time it starts — your
  existing kids/jobs/history are preserved, but you'll need to
  re-upload their photos and icons once, since the old files are gone.)

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

## Why did my images go blank after a restart? (and how persistence works now)

If you saw this on an earlier version of the app: it saved uploaded images
as separate files under `static/uploads/...`, while the kid/job records
themselves lived in `jobs.db`. Those two things being blank vs. present
after a restart is a strong sign that only one of them was on storage that
actually survives a restart — for example:

- **Containers** (Docker, etc.): each container has its own writable
  filesystem layer that resets when the container is recreated, unless you
  explicitly mount a volume for it. If `jobs.db` was on a mounted volume
  but `static/uploads/` wasn't (or vice versa), one persists and the other
  doesn't.
- **PaaS platforms** (Heroku, Render free tier, Railway, etc.): these often
  wipe the whole filesystem on every restart/redeploy unless you're using
  their specific "persistent disk" feature — plain local files don't survive
  by default.
- **Git-based deploys**: if `static/uploads/` was excluded via `.gitignore`
  (as it was here) and your deploy process re-checks-out the repo, freshly
  uploaded images that were never committed simply aren't there after the
  next deploy, even though the code and an empty/older `jobs.db` are.

The fix in this version: **images are now stored as bytes inside
`jobs.db` itself**, served back out through small `/media/...` routes
(see `app.py`). There's only one artifact to keep persistent — the database
file — so as long as you already know `jobs.db` survives your restarts
(which it evidently does, since your kid/job records were intact), the
images now will too.

If you'd rather keep images as plain files instead of in the database (e.g.
you expect a very large photo library and don't want to bloat the sqlite
file), the underlying requirement is the same either way: whatever
directory holds them needs to sit on storage that survives both process
restarts and redeploys — a Docker named volume, a cloud provider's
persistent disk, or external object storage (S3, etc.) — not the app's own
ephemeral working directory.



- **Daily** jobs reset at midnight (local server time).
- **Weekly** jobs reset at the start of the week (Monday).
- A job can only be marked done once per period; the button disables
  itself and shows when it resets.

## Ideas for extending later

- PIN per kid instead of a shared picker (kept simple here since it's for
  siblings sharing one household screen).
- Push notifications when a job streak is broken.
- CSV export of completions from the stats page.
