import uuid

from models.errors import LifecycleError


def uid(value: str) -> str:
    """Normalise a path/body id; a malformed one is a not-found, not a 500."""
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise LifecycleError("not_found", "not found") from None
