import { notFound, redirect } from "next/navigation";

import { auth } from "@/auth";
import { ApproverPicker } from "@/components/ApproverPicker";
import { ChangeForm } from "@/components/ChangeForm";
import { FileDrop } from "@/components/FileDrop";
import { RevisionRemoveList } from "@/components/RevisionRemoveList";
import { ApiError, apiFetch } from "@/lib/api";
import type { ChangeDetail, DocumentSummary, UserOut } from "@/lib/types";

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

export default async function EditChangePage({
  params,
}: PageProps<"/changes/[id]/edit">) {
  const { id } = await params;
  const session = await auth();
  const viewerId = session?.user?.id;

  let change: ChangeDetail;
  let documents: DocumentSummary[];
  let users: UserOut[];
  try {
    [change, documents, users] = await Promise.all([
      apiFetch<ChangeDetail>(`/changes/${encodeURIComponent(id)}`),
      apiFetch<DocumentSummary[]>("/documents"),
      apiFetch<UserOut[]>("/users"),
    ]);
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

  if (change.status !== "initiate") redirect(`/changes/${id}`);

  const released = documents.filter((d) => d.current_revision_id !== null);
  const candidates = users.filter((u) => !u.deactivated && u.id !== viewerId);

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">
        Edit {change.number}
      </h1>
      <ChangeForm
        changeId={change.id}
        initial={{
          title: change.title,
          description: change.description,
          reason: change.reason,
          justification: change.justification,
        }}
      />
      <Section title="Documents">
        <RevisionRemoveList
          changeId={change.id}
          revisions={change.revisions.map((r) => ({
            id: r.id,
            filename: r.original_filename,
            documentTitle: r.document_title,
          }))}
        />
        <FileDrop
          changeId={change.id}
          documents={released.map((d) => ({ id: d.id, title: d.title }))}
        />
      </Section>
      <Section title="Approvers">
        <ApproverPicker
          changeId={change.id}
          users={candidates.map((u) => ({
            id: u.id,
            name: u.name,
            role: u.role,
          }))}
          selected={change.approvers.map((a) => a.user_id)}
        />
      </Section>
    </div>
  );
}
