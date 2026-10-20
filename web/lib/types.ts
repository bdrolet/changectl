// Mirrors api/schemas.py. Dates are ISO strings.

export interface UserOut {
  id: string;
  email: string;
  name: string;
  role: string;
  is_doc_manager: boolean;
  deactivated: boolean;
}

export interface ChangeSummary {
  id: string;
  number: string;
  title: string;
  status: string;
  created_by: string;
  created_by_name: string;
  created_at: string;
  documents: string[];
  waiting_on: string[];
}

export interface RevisionOut {
  id: string;
  document_id: string;
  document_title: string;
  revision_number: number | null;
  original_filename: string;
  content_type: string;
  byte_size: number;
  sha256: string;
  has_redline: boolean;
  uploaded_by: string;
  uploaded_at: string;
  released_at: string | null;
  superseded_at: string | null;
  next_revision_number: number | null;
}

export interface ApproverOut {
  user_id: string;
  name: string;
  email: string;
  role: string;
  state: "signed" | "pending" | "changes_requested";
}

export interface ApprovalOut {
  id: string;
  user_id: string;
  name: string;
  email: string;
  decision: string;
  comment: string | null;
  signed_at: string;
  voided_at: string | null;
  voided_reason: string | null;
}

export interface CommentOut {
  id: string;
  user_id: string;
  name: string;
  body: string;
  created_at: string;
}

export interface EventOut {
  id: string;
  at: string;
  actor_user_id: string | null;
  actor_name: string | null;
  entity_type: string;
  entity_id: string;
  action: string;
  detail: Record<string, unknown>;
}

export interface ChangeDetail extends ChangeSummary {
  description: string;
  reason: string;
  justification: string;
  cutin_date: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  closed_at: string | null;
  revisions: RevisionOut[];
  approvers: ApproverOut[];
  approvals: ApprovalOut[];
  comments: CommentOut[];
  events: EventOut[];
}

export interface DocumentSummary {
  id: string;
  title: string;
  current_revision_id: string | null;
  revision_number: number | null;
  released_at: string | null;
  released_by_name: string | null;
  original_filename: string | null;
  rank: number;
}

export interface DocumentRevisionOut extends RevisionOut {
  change_id: string;
  change_number: string;
  change_title: string;
  change_status: string;
  cutin_date: string | null;
  approvals: Record<string, unknown>[];
}

export interface DocumentDetail {
  id: string;
  title: string;
  created_at: string;
  current_revision_id: string | null;
  revisions: DocumentRevisionOut[];
}
