import { ApiError } from "@/lib/api";

// Keep in sync with models/errors.py (LifecycleError codes) plus the auth
// codes api/errors.py can return.
export const CODES = [
  "not_found",
  "forbidden",
  "wrong_status",
  "locked",
  "self_approval",
  "not_an_approver",
  "no_approvers",
  "no_revisions",
  "invalid_file",
  "too_large",
  "type_mismatch",
  "document_busy",
  "cutin_required",
  "comment_required",
  "duplicate_email",
  "pending_approver",
  "last_doc_manager",
  "missing_bearer",
  "invalid_token",
  "not_invited",
  "doc_manager_required",
  "email_unverified",
  "identity_mismatch",
] as const;

const COPY: Record<(typeof CODES)[number], string> = {
  not_found: "That doesn't exist or you can't see it.",
  forbidden: "You don't have permission to do that.",
  wrong_status: "That isn't possible in this change's current status.",
  locked: "This change is locked; only drafts can be edited.",
  self_approval: "You can't approve your own change.",
  not_an_approver: "You aren't a named approver on this change.",
  no_approvers: "Pick at least one approver before submitting.",
  no_revisions: "Attach at least one file before submitting.",
  invalid_file: "That file couldn't be read. Upload a valid PDF, DOCX or XLSX.",
  too_large: "Files must be 25 MB or smaller",
  type_mismatch:
    "A new revision must be the same file type as the document it replaces.",
  document_busy: "That document already has a revision in an open change.",
  cutin_required: "Enter a cut-in date before releasing.",
  comment_required: "Add a comment explaining what needs to change.",
  duplicate_email: "A user with that email already exists.",
  pending_approver:
    "Finish or reassign the open changes before deactivating this user.",
  last_doc_manager: "There must be at least one active doc manager.",
  missing_bearer: "Your session has expired. Sign in again.",
  invalid_token: "Your session has expired. Sign in again.",
  not_invited: "You're not invited to this workspace.",
  doc_manager_required: "Only doc managers can do that.",
  email_unverified: "Your Google email address isn't verified.",
  identity_mismatch:
    "This Google account doesn't match the one that first signed in for your email.",
};

const FALLBACK = "Something went wrong.";

export function describe(detail: string): string {
  return Object.hasOwn(COPY, detail)
    ? COPY[detail as (typeof CODES)[number]]
    : FALLBACK;
}

export function describeError(e: unknown): string {
  if (!(e instanceof ApiError)) return FALLBACK;
  const text = describe(e.detail);
  return e.changes?.length ? `${text}: ${e.changes.join(", ")}` : text;
}
