import { bytes } from "@/lib/format";
import type { RevisionOut } from "@/lib/types";

export function RevisionList({ revisions }: { revisions: RevisionOut[] }) {
  if (revisions.length === 0) {
    return <p className="text-sm text-zinc-600">No documents attached.</p>;
  }
  return (
    <ul className="divide-y divide-zinc-100 text-sm">
      {revisions.map((r) => (
        <li key={r.id} className="flex flex-wrap items-center gap-x-3 py-2">
          <span className="font-medium">{r.original_filename}</span>
          <span className="text-zinc-600">{bytes(r.byte_size)}</span>
          <span>{r.document_title}</span>
          <span className="text-zinc-600">
            {r.revision_number === null
              ? "pending"
              : `Rev ${r.revision_number}`}
          </span>
          {r.has_redline && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
              redline
            </span>
          )}
          <span className="ml-auto flex gap-3">
            <a
              href={`/api/download/${r.id}`}
              className="text-blue-700 hover:underline"
            >
              Download
            </a>
            {r.has_redline && (
              <a
                href={`/api/download/${r.id}?which=redline`}
                className="text-blue-700 hover:underline"
              >
                Download redline
              </a>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}
