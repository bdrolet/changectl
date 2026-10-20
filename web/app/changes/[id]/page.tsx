import { notFound, redirect } from "next/navigation";

import { ApproverList } from "@/components/ApproverList";
import { CommentList } from "@/components/CommentList";
import { HistoryPanel } from "@/components/HistoryPanel";
import { RevisionList } from "@/components/RevisionList";
import { StatusPill } from "@/components/StatusPill";
import { ApiError, apiFetch } from "@/lib/api";
import { dateOnly } from "@/lib/format";
import type { ChangeDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export default async function ChangeDetailPage({
  params,
}: PageProps<"/changes/[id]">) {
  const { id } = await params;

  let change: ChangeDetail;
  try {
    change = await apiFetch<ChangeDetail>(`/changes/${encodeURIComponent(id)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect("/signin");
    if (e instanceof ApiError && e.status === 404) notFound();
    return (
      <div
        role="alert"
        className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800"
      >
        {e instanceof Error ? e.message : "Failed to load change"}
      </div>
    );
  }

  const fields: [string, string][] = [
    ["Description", change.description],
    ["Reason", change.reason],
    ["Justification", change.justification],
  ];
  if (change.cutin_date)
    fields.push(["Cut-in date", dateOnly(change.cutin_date)]);

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-center gap-3">
        <span className="text-zinc-600">{change.number}</span>
        <h1 className="text-2xl font-semibold">{change.title}</h1>
        <StatusPill status={change.status} />
      </header>

      <div id="actions" />

      <dl className="space-y-3 text-sm">
        {fields.map(([label, value]) => (
          <div key={label}>
            <dt className="font-medium text-zinc-600">{label}</dt>
            <dd className="whitespace-pre-wrap">{value}</dd>
          </div>
        ))}
      </dl>

      <Section title="Documents">
        <RevisionList revisions={change.revisions} />
      </Section>
      <Section title="Approvers">
        <ApproverList approvers={change.approvers} />
      </Section>
      <Section title="Comments">
        <CommentList comments={change.comments} />
      </Section>
      <Section title="History">
        <HistoryPanel events={change.events} />
      </Section>
    </div>
  );
}
