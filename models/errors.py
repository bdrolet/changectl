class LifecycleError(Exception):
    """A business-rule refusal. `code` is stable and machine-readable."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
