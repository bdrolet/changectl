import { signIn } from "@/auth";

export default async function SignInPage({
  searchParams,
}: PageProps<"/signin">) {
  const { error } = await searchParams;

  return (
    <div className="mx-auto mt-24 max-w-sm text-center">
      <h1 className="text-2xl font-semibold">changectl</h1>
      <p className="mt-2 text-zinc-600">Sign in to continue.</p>
      {error && (
        <p role="alert" className="mt-4 text-sm text-red-700">
          Sign-in could not be completed. Try again in a moment.
        </p>
      )}
      <form
        className="mt-6"
        action={async () => {
          "use server";
          await signIn("google", { redirectTo: "/changes" });
        }}
      >
        <button
          type="submit"
          className="w-full rounded bg-blue-700 px-4 py-2 font-medium text-white hover:bg-blue-800"
        >
          Sign in with Google
        </button>
      </form>
    </div>
  );
}
