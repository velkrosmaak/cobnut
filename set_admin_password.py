"""
Generate a password hash for the admin area and print the .env line to add.

Usage:
    python set_admin_password.py
"""
import getpass
from werkzeug.security import generate_password_hash

if __name__ == "__main__":
    password = getpass.getpass("New admin password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords did not match.")
    hashed = generate_password_hash(password)
    print("\nAdd this line to your .env file:\n")
    print(f"ADMIN_PASSWORD_HASH={hashed}")
