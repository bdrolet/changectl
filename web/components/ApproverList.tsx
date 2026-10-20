import type { ApproverOut } from "@/lib/types";

const STATE: Record<ApproverOut["state"], { label: string; cls: string }> = {
  signed: { label: "signed", cls: "bg-green-100 text-green-800" },
  pending: { label: "pending", cls: "bg-zinc-100 text-zinc-700" },
  changes_requested: {
    label: "changes requested",
    cls: "bg-amber-100 text-amber-800",
  },
};

export function ApproverList({ approvers }: { approvers: ApproverOut[] }) {
  if (approvers.length === 0) {
    return <p className="text-sm text-zinc-600">No approvers.</p>;
  }
  return (
    <ul className="divide-y divide-zinc-100 text-sm">
      {approvers.map((a) => (
        <li key={a.user_id} className="flex items-center gap-3 py-2">
          <span className="font-medium">{a.name}</span>
          <span className="text-zinc-600">{a.role}</span>
          <span
            className={`ml-auto rounded-full px-2 py-0.5 text-xs font-medium ${STATE[a.state].cls}`}
          >
            {STATE[a.state].label}
          </span>
        </li>
      ))}
    </ul>
  );
}
