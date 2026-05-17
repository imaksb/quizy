import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def pytest_configure() -> None:
    os.environ.setdefault("AUTH_SECRET_KEY", "test-secret-key-with-32-bytes-minimum")
    os.environ.setdefault("FAKE_HASH", "test-fake-hash")
    os.environ.setdefault("POSTGRES_USER", "quizy")
    os.environ.setdefault("POSTGRES_DB", "quizy")
    os.environ.setdefault("POSTGRES_PASSWORD", "quizy")
    os.environ.setdefault("POSTGRES_HOST", "localhost")
    os.environ.setdefault("POSTGRES_PORT", "5432")
    os.environ.setdefault("GOOGLE_CLIENT_SECRET", "google-secret")
    os.environ.setdefault("GOOGLE_CLIENT_ID", "google-client")
    os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost/auth/callback")
    os.environ.setdefault("FRONTEND_ADMIN_URL", "http://localhost:3000")
    os.environ.setdefault("FRONTEND_CLIENT_URL", "http://localhost:3001")
    os.environ.setdefault("OPENAPI_SWAGGER_PASSWORD", "swagger-password")
    os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
