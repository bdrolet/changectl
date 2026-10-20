import { dateOnly } from "@/lib/format";
import type { EventOut } from "@/lib/types";

export function HistoryPanel({ events }: { events: EventOut[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-zinc-600">No history.</p>;
  }
  const newestFirst = [...events].sort(
    (a, b) => Date.parse(b.at) - Date.parse(a.at),
  );
  return (
    <ul className="space-y-2 text-sm">
      {newestFirst.map((e) => (
        <li key={e.id}>
          <span className="text-zinc-600">
            {dateOnly(e.at)} {new Date(e.at).toISOString().slice(11, 16)}
          </span>{" "}
          <span className="font-medium">{e.actor_name ?? "system"}</span>{" "}
          <span>{e.action}</span>
          {Object.keys(e.detail).length > 0 && (
            <code className="ml-2 break-all rounded bg-zinc-100 px-1 text-xs">
              {JSON.stringify(e.detail)}
            </code>
          )}
        </li>
      ))}
    </ul>
  );
}
