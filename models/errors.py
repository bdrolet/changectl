class LifecycleError(Exception):
    """A business-rule refusal. `code` is stable and machine-readable.

    Codes: not_found, forbidden, wrong_status, locked, self_approval,
    not_an_approver, no_approvers, no_revisions, invalid_file, too_large,
    type_mismatch, document_busy, cutin_required, comment_required.
    """

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
