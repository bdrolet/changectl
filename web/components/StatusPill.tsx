const STYLES: Record<string, string> = {
  initiate: "bg-zinc-100 text-zinc-700",
  approval: "bg-amber-100 text-amber-800",
  implementation: "bg-blue-100 text-blue-800",
  closed: "bg-green-100 text-green-800",
};

export function StatusPill({ status }: { status: string }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${STYLES[status] ?? STYLES.initiate}`}
    >
      {status}
    </span>
  );
}
