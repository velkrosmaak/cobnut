import os
import uuid
from functools import wraps

from flask import current_app, request, Response
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename


def allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def save_upload(file_storage, subfolder):
    """Save an uploaded image under static/uploads/<subfolder>/ with a random
    prefix to avoid collisions. Returns the stored filename, or None if no
    file was provided."""
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        raise ValueError("Unsupported image type. Use png, jpg, jpeg, gif, or webp.")

    filename = secure_filename(file_storage.filename)
    unique_name = f"{uuid.uuid4().hex[:10]}_{filename}"
    folder = current_app.config["UPLOAD_FOLDERS"][subfolder]
    os.makedirs(folder, exist_ok=True)
    file_storage.save(os.path.join(folder, unique_name))
    return unique_name


def delete_upload(filename, subfolder):
    if not filename:
        return
    folder = current_app.config["UPLOAD_FOLDERS"][subfolder]
    path = os.path.join(folder, filename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


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
        {"WWW-Authenticate": 'Basic realm="Chores Admin"'},
    )


def admin_required(view):
    """HTTP Basic Auth guard for /admin routes. This works regardless of how
    the app is deployed (dev server, gunicorn, behind a proxy) unlike a plain
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
