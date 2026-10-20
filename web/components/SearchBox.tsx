export function SearchBox({ q }: { q: string }) {
  return (
    <form method="get" action="/documents" className="flex max-w-xl gap-2">
      <input
        type="search"
        name="q"
        defaultValue={q}
        placeholder="Search released documents"
        aria-label="Search released documents"
        className="w-full rounded border border-zinc-300 px-2 py-1 text-sm"
      />
      <button
        type="submit"
        className="rounded bg-zinc-900 px-3 py-1.5 text-sm text-white"
      >
        Search
      </button>
    </form>
  );
}
