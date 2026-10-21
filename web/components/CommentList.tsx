import { dateOnly } from "@/lib/format";
import type { CommentOut } from "@/lib/types";

export function CommentList({ comments }: { comments: CommentOut[] }) {
  if (comments.length === 0) {
    return <p className="text-sm text-zinc-600">No comments.</p>;
  }
  return (
    <ul className="space-y-3 text-sm">
      {comments.map((c) => (
        <li key={c.id}>
          <div className="text-zinc-600">
            <span className="font-medium text-zinc-900">{c.name}</span>{" "}
            {dateOnly(c.created_at)}
          </div>
          <p className="whitespace-pre-wrap">{c.body}</p>
        </li>
      ))}
    </ul>
  );
}
