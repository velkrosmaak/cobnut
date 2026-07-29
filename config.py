import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'chores.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_ROOT = os.path.join(BASE_DIR, "static", "uploads")
    UPLOAD_FOLDERS = {
        "kids": os.path.join(UPLOAD_ROOT, "kids"),
        "chores": os.path.join(UPLOAD_ROOT, "chores"),
        "tokens": os.path.join(UPLOAD_ROOT, "tokens"),
    }
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8MB uploads

    # Admin basic-auth credentials (see set_admin_password.py to generate the hash)
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")
