import Link from "next/link";

import { Alert } from "@/components/Alert";
import { SearchBox } from "@/components/SearchBox";
import { apiFetch, redirectIfSignedOut } from "@/lib/api";
import { dateOnly } from "@/lib/format";
import type { DocumentSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function DocumentsPage({
  searchParams,
}: PageProps<"/documents">) {
  const raw = (await searchParams).q;
  const q = (Array.isArray(raw) ? raw[0] : raw)?.trim() ?? "";

  let docs: DocumentSummary[] = [];
  let error: string | null = null;
  try {
    docs = await apiFetch<DocumentSummary[]>(
      q ? `/documents?q=${encodeURIComponent(q)}` : "/documents",
    );
  } catch (e) {
    redirectIfSignedOut(e);
    error = e instanceof Error ? e.message : "Failed to load documents";
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Documents</h1>
      <SearchBox q={q} />
      <Alert message={error} />
      {!error && docs.length === 0 && (
        <p className="text-sm text-zinc-600">
          {q ? "No released documents match." : "No released documents yet."}
        </p>
      )}
      {docs.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead className="text-zinc-600">
            <tr>
              <th className="py-2 pr-4 font-medium">Title</th>
              <th className="py-2 pr-4 font-medium">Current revision</th>
              <th className="py-2 pr-4 font-medium">Released</th>
              <th className="py-2 pr-4 font-medium">Released by</th>
              <th className="py-2 font-medium">File</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {docs.map((d) => (
              <tr key={d.id}>
                <td className="py-2 pr-4">
                  <Link
                    href={`/documents/${d.id}`}
                    className="text-blue-700 hover:underline"
                  >
                    {d.title}
                  </Link>
                </td>
                <td className="py-2 pr-4">
                  {d.revision_number === null ? "" : `Rev ${d.revision_number}`}
                </td>
                <td className="py-2 pr-4">
                  {d.released_at ? dateOnly(d.released_at) : ""}
                </td>
                <td className="py-2 pr-4">{d.released_by_name ?? ""}</td>
                <td className="py-2">{d.original_filename ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
