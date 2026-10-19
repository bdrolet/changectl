import Link from "next/link";

export default async function NotInvitedPage({
  searchParams,
}: PageProps<"/not-invited">) {
  const { email } = await searchParams;
  const address = typeof email === "string" && email ? email : null;

  return (
    <div className="mx-auto mt-24 max-w-md text-center">
      <h1 className="text-2xl font-semibold">You&apos;re not on the list yet</h1>
      <p className="mt-3 text-zinc-600">
        Ask your doc manager to invite {address ?? "your email address"} to
        changectl.
      </p>
      <Link
        href="/api/auth/signout"
        className="mt-6 inline-block text-sm text-blue-700 underline"
      >
        Sign out
      </Link>
    </div>
  );
}
