import { ChangeForm } from "@/components/ChangeForm";

export const dynamic = "force-dynamic";

export default function NewChangePage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">New change</h1>
      <ChangeForm />
    </div>
  );
}
