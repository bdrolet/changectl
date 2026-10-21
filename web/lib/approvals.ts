import type { ApprovalOut } from "@/lib/types";

/** Each user's most recent approval row (live or voided), keyed by user id. */
export function latestApprovalByUser(
  approvals: ApprovalOut[],
): Map<string, ApprovalOut> {
  const latest = new Map<string, ApprovalOut>();
  for (const a of approvals) {
    const seen = latest.get(a.user_id);
    if (!seen || Date.parse(a.signed_at) > Date.parse(seen.signed_at)) {
      latest.set(a.user_id, a);
    }
  }
  return latest;
}
