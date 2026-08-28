#!/usr/bin/env python3
"""Generate bcrypt password hash for authentication."""

import bcrypt
import sys


def generate_hash(password: str) -> str:
    """Generate bcrypt hash for a password."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = input("Enter password to hash: ")

    hashed = generate_hash(password)
    print(f"\nPassword hash (use this for AUTH_PASSWORD_HASH):\n{hashed}")
