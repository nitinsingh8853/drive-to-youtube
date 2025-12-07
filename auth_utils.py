import os
import logging
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from config import TOKEN_FILE, SCOPES

logger = logging.getLogger('auth_utils')


def load_credentials():
    """Load saved credentials from TOKEN_FILE. Refresh if expired."""
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    except Exception as e:
        logger.exception("Failed to read credentials file: %s", e)
        return None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
        except Exception as e:
            logger.exception('Failed to refresh credentials: %s', e)
            return None
    return creds


def save_credentials(creds):
    """Save credentials to TOKEN_FILE."""
    with open(TOKEN_FILE, 'w') as f:
        f.write(creds.to_json())
    logger.info('Saved credentials to %s', TOKEN_FILE)


def revoke_credentials():
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
