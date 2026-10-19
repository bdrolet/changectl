from dataclasses import dataclass

import google.auth.exceptions
import google.auth.transport.requests
from google.oauth2 import id_token


@dataclass
class Claims:
    sub: str
    email: str
    email_verified: bool
    name: str | None


def verify_id_token(token: str, audience: str) -> Claims:
    """Verify a Google ID token; raise ValueError on any failure."""
    try:
        info = id_token.verify_oauth2_token(
            token, google.auth.transport.requests.Request(), audience
        )
        return Claims(
            sub=info["sub"],
            email=info["email"],
            email_verified=bool(info.get("email_verified")),
            name=info.get("name"),
        )
    except ValueError:
        raise
    except (google.auth.exceptions.GoogleAuthError, KeyError) as exc:
        raise ValueError(str(exc)) from exc
