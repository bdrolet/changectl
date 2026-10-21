import Link from "next/link";

import { StatusPill } from "@/components/StatusPill";
import { relativeAge } from "@/lib/format";
import type { ChangeSummary } from "@/lib/types";

export function ChangeTable({ changes }: { changes: ChangeSummary[] }) {
  if (changes.length === 0) {
    return <p className="text-sm text-zinc-600">No changes.</p>;
  }
  return (
    <table className="w-full text-left text-sm">
      <thead className="border-b border-zinc-200 text-zinc-600">
        <tr>
          <th className="py-2 pr-3 font-medium">Number</th>
          <th className="py-2 pr-3 font-medium">Title</th>
          <th className="py-2 pr-3 font-medium">Documents</th>
          <th className="py-2 pr-3 font-medium">Created by</th>
          <th className="py-2 pr-3 font-medium">Waiting on</th>
          <th className="py-2 font-medium">Age</th>
        </tr>
      </thead>
      <tbody>
        {changes.map((c) => (
          <tr key={c.id} className="border-b border-zinc-100 align-top">
            <td className="whitespace-nowrap py-2 pr-3">
              <Link
                href={`/changes/${c.id}`}
                className="font-medium text-blue-700 hover:underline"
              >
                {c.number}
              </Link>
              <div className="mt-1">
                <StatusPill status={c.status} />
              </div>
            </td>
            <td className="py-2 pr-3">
              <Link href={`/changes/${c.id}`} className="hover:underline">
                {c.title}
              </Link>
            </td>
            <td className="py-2 pr-3">{c.documents.join(", ")}</td>
            <td className="py-2 pr-3">{c.created_by_name}</td>
            <td className="py-2 pr-3">
              {c.waiting_on.length ? c.waiting_on.join(", ") : "—"}
            </td>
            <td className="whitespace-nowrap py-2">
              {relativeAge(c.created_at)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
