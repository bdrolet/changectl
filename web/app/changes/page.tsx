import Link from "next/link";
import { redirect } from "next/navigation";

import { ChangeTable } from "@/components/ChangeTable";
import { ApiError, apiFetch } from "@/lib/api";
import type { ChangeSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

const TABS = [
  { label: "All", status: undefined },
  { label: "Initiate", status: "initiate" },
  { label: "Approval", status: "approval" },
  { label: "Implementation", status: "implementation" },
  { label: "Closed", status: "closed" },
] as const;

const RANK: Record<string, number> = {
  initiate: 0,
  approval: 1,
  implementation: 2,
  closed: 3,
};

export default async function ChangesPage({
  searchParams,
}: PageProps<"/changes">) {
  const raw = (await searchParams).status;
  const requested = typeof raw === "string" ? raw : undefined;
  const status = TABS.find((t) => t.status === requested)?.status;

  let changes: ChangeSummary[] = [];
  let error: string | null = null;
  try {
    changes = await apiFetch<ChangeSummary[]>(
      status ? `/changes?status=${status}` : "/changes",
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect("/signin");
    error = e instanceof Error ? e.message : "Failed to load changes";
  }
  // Array.prototype.sort is stable, so the API's newest-first order holds
  // within each status group.
  const sorted = [...changes].sort(
    (a, b) => (RANK[a.status] ?? 4) - (RANK[b.status] ?? 4),
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Changes</h1>
        <Link
          href="/changes/new"
          className="rounded bg-zinc-900 px-3 py-1.5 text-sm text-white"
        >
          New change
        </Link>
      </div>
      <nav className="flex gap-4 border-b border-zinc-200 text-sm">
        {TABS.map((t) => {
          const active = t.status === status;
          return (
            <Link
              key={t.label}
              href={t.status ? `/changes?status=${t.status}` : "/changes"}
              aria-current={active ? "page" : undefined}
              className={`-mb-px border-b-2 pb-2 ${active ? "border-blue-700 font-medium text-blue-700" : "border-transparent hover:text-blue-700"}`}
            >
              {t.label}
            </Link>
          );
        })}
      </nav>
      {error ? (
        <div
          role="alert"
          className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800"
        >
          {error}
        </div>
      ) : (
        <ChangeTable changes={sorted} />
      )}
    </div>
  );
}
