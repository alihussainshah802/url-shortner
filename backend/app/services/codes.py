import secrets
import string

ALPHABET = string.digits + string.ascii_uppercase + string.ascii_lowercase  # base62


def generate_code(length: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))
