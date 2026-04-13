from copy import deepcopy
from urllib.parse import urlencode

from app.core.settings import settings


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

_GOOGLE_REDIRECT_PARAMS = {
    "client_id": settings.GOOGLE_CLIENT_ID,
    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
    "response_type": "code",
    "scope": "openid email profile",
    "access_type": "offline",
    "prompt": "consent",
}

def get_google_redirect_link() -> str:
    """
    Returns the Google Redirect Link to authorize via GOOGLE oauth2
    :return:
    """
    params = deepcopy(_GOOGLE_REDIRECT_PARAMS)
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
