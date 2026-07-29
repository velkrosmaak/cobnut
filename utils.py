from functools import wraps

from flask import current_app, request, Response
from werkzeug.security import check_password_hash


def allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def read_image_upload(file_storage):
    """Read an uploaded image into memory as (bytes, mimetype), for storage
    directly in the database. Returns None if no file was provided.

    Storing the bytes in the database (rather than saving to a file on disk)
    means the images live wherever jobs.db lives — they can't quietly
    disappear because of an ephemeral container filesystem, a redeploy that
    doesn't carry over an untracked uploads folder, or similar, as long as
    the database file itself is on persistent storage."""
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        raise ValueError("Unsupported image type. Use png, jpg, jpeg, gif, or webp.")

    data = file_storage.read()
    if not data:
        return None
    mimetype = file_storage.mimetype or "application/octet-stream"
    return data, mimetype


def check_admin_auth(username, password):
    cfg = current_app.config
    if not cfg.get("ADMIN_PASSWORD_HASH"):
        # No hash configured yet: fall back to a plain-text default so the
        # admin area is still reachable during first-time setup. Set
        # ADMIN_PASSWORD_HASH via set_admin_password.py for real deployments.
        return username == cfg["ADMIN_USERNAME"] and password == "admin"
    return (
        username == cfg["ADMIN_USERNAME"]
        and check_password_hash(cfg["ADMIN_PASSWORD_HASH"], password)
    )


def authenticate_response():
    return Response(
        "Admin area: authentication required.", 401,
        {"WWW-Authenticate": 'Basic realm="Jobs Admin"'},
    )


def admin_required(view):
    """HTTP Basic Auth guard for /admin routes. This works regardless of how
    the app is deployed (dev server, gunicorn, behind any proxy) unlike a plain
    .htaccess file, which only applies when Apache itself is serving/proxying
    the path with AllowOverride enabled. See README for the .htaccess-based
    alternative if you're deploying under Apache + mod_wsgi."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_admin_auth(auth.username, auth.password):
            return authenticate_response()
        return view(*args, **kwargs)

    return wrapped
