import { latestApprovalByUser } from "@/lib/approvals";
import { dateOnly, timeUtc } from "@/lib/format";
import type { ApprovalOut, ApproverOut } from "@/lib/types";

const STATE: Record<ApproverOut["state"], { label: string; cls: string }> = {
  signed: { label: "signed", cls: "bg-green-100 text-green-800" },
  pending: { label: "pending", cls: "bg-zinc-100 text-zinc-700" },
  changes_requested: {
    label: "changes requested",
    cls: "bg-amber-100 text-amber-800",
  },
};

const DECISION: Record<string, string> = {
  approved: "Approved",
  changes_requested: "Requested changes",
};

function LatestApproval({ approval }: { approval: ApprovalOut }) {
  const voided = approval.voided_at !== null;
  return (
    <div className={`text-xs ${voided ? "text-zinc-500" : "text-zinc-700"}`}>
      <p>
        <span className={voided ? "line-through" : "font-medium"}>
          {DECISION[approval.decision] ?? approval.decision}
        </span>{" "}
        {dateOnly(approval.signed_at)} {timeUtc(approval.signed_at)}
        {voided && (
          <span>
            {" "}
            · voided
            {approval.voided_reason ? `: ${approval.voided_reason}` : ""}
          </span>
        )}
      </p>
      {approval.comment && (
        <p className="mt-0.5 whitespace-pre-wrap">“{approval.comment}”</p>
      )}
    </div>
  );
}

export function ApproverList({
  approvers,
  approvals = [],
}: {
  approvers: ApproverOut[];
  approvals?: ApprovalOut[];
}) {
  if (approvers.length === 0) {
    return <p className="text-sm text-zinc-600">No approvers.</p>;
  }
  const latest = latestApprovalByUser(approvals);
  return (
    <ul className="divide-y divide-zinc-100 text-sm">
      {approvers.map((a) => {
        const approval = latest.get(a.user_id);
        return (
          <li key={a.user_id} className="space-y-1 py-2">
            <div className="flex items-center gap-3">
              <span className="font-medium">{a.name}</span>
              <span className="text-zinc-600">{a.role}</span>
              <span
                className={`ml-auto rounded-full px-2 py-0.5 text-xs font-medium ${STATE[a.state].cls}`}
              >
                {STATE[a.state].label}
              </span>
            </div>
            {approval && <LatestApproval approval={approval} />}
          </li>
        );
      })}
    </ul>
  );
}
