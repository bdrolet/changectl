"use server";

import { revalidatePath } from "next/cache";

import { ApiError, apiFetch } from "@/lib/api";
import { describeError } from "@/lib/errors";

export type ActionResult = { ok: true } | { ok: false; error: string };

function field(form: FormData, name: string): string {
  const v = form.get(name);
  return typeof v === "string" ? v : "";
}

export async function inviteUser(form: FormData): Promise<ActionResult> {
  try {
    await apiFetch("/users", {
      method: "POST",
      body: JSON.stringify({
        email: field(form, "email").trim(),
        name: field(form, "name").trim(),
        role: field(form, "role"),
        is_doc_manager: form.get("is_doc_manager") !== null,
      }),
    });
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: describeError(e) };
    throw e;
  }
  revalidatePath("/users");
  return { ok: true };
}

export async function updateUser(
  userId: string,
  name: string,
  patch: { role?: string; is_doc_manager?: boolean; deactivated?: boolean },
): Promise<ActionResult> {
  try {
    await apiFetch(`/users/${encodeURIComponent(userId)}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.detail === "pending_approver" && e.changes?.length) {
        return {
          ok: false,
          error: `Finish or reassign ${e.changes.join(", ")} before deactivating ${name}.`,
        };
      }
      return { ok: false, error: describeError(e) };
    }
    throw e;
  }
  revalidatePath("/users");
  return { ok: true };
}
