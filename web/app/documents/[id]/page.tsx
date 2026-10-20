import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { StatusPill } from "@/components/StatusPill";
import { ApiError, apiFetch } from "@/lib/api";
import { bytes, dateOnly } from "@/lib/format";
import type { DocumentDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

function approvalLabel(a: Record<string, unknown>): string {
  const name = typeof a.name === "string" ? a.name : "";
  const at = typeof a.signed_at === "string" ? dateOnly(a.signed_at) : "";
  return at ? `${name} (${at})` : name;
}

export default async function DocumentPage({
  params,
}: PageProps<"/documents/[id]">) {
  const { id } = await params;

  let doc: DocumentDetail;
  try {
    doc = await apiFetch<DocumentDetail>(
      `/documents/${encodeURIComponent(id)}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect("/signin");
    if (e instanceof ApiError && e.status === 404) notFound();
    return (
      <div
        role="alert"
        className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800"
      >
        {e instanceof Error ? e.message : "Failed to load document"}
      </div>
    );
  }

  const current = doc.revisions.find((r) => r.id === doc.current_revision_id);

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">{doc.title}</h1>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Current revision</h2>
        {current ? (
          <p className="flex flex-wrap items-center gap-x-3 text-sm">
            <span className="font-medium">Rev {current.revision_number}</span>
            <span>{current.original_filename}</span>
            <span className="text-zinc-600">{bytes(current.byte_size)}</span>
            <a
              href={`/api/download/${current.id}`}
              className="text-blue-700 hover:underline"
            >
              Download
            </a>
          </p>
        ) : (
          <p className="text-sm text-zinc-600">No released revision yet.</p>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Revisions</h2>
        <ul className="divide-y divide-zinc-100 text-sm">
          {doc.revisions.map((r) => (
            <li key={r.id} className="space-y-1 py-3">
              <div className="flex flex-wrap items-center gap-x-3">
                <span className="font-medium">
                  {r.revision_number === null
                    ? "pending"
                    : `Rev ${r.revision_number}`}
                </span>
                <Link
                  href={`/changes/${r.change_id}`}
                  className="text-blue-700 hover:underline"
                >
                  {r.change_number} {r.change_title}
                </Link>
                <StatusPill status={r.change_status} />
                {r.cutin_date && (
                  <span className="text-zinc-600">
                    Cut-in {dateOnly(r.cutin_date)}
                  </span>
                )}
                {r.superseded_at && (
                  <span className="rounded-full bg-zinc-200 px-2 py-0.5 text-xs font-medium text-zinc-700">
                    superseded
                  </span>
                )}
              </div>
              {r.approvals.length > 0 && (
                <p className="text-zinc-600">
                  Approved by {r.approvals.map(approvalLabel).join(", ")}
                </p>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
