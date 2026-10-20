import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/auth", () => ({ auth: vi.fn() }));
vi.mock("next/headers", () => ({ headers: vi.fn() }));
vi.mock("next-auth/jwt", () => ({ getToken: vi.fn() }));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  apiFetch: vi.fn(),
}));

import { revalidatePath } from "next/cache";

import { ApiError, apiFetch } from "@/lib/api";

import { inviteUser, updateUser } from "./actions";

describe("updateUser", () => {
  beforeEach(() => vi.clearAllMocks());

  it("names the open changes and the user on pending_approver", async () => {
    vi.mocked(apiFetch).mockRejectedValueOnce(
      new ApiError(409, "pending_approver", "pending", ["CHG-0004"]),
    );
    expect(await updateUser("u1", "Dana", { deactivated: true })).toEqual({
      ok: false,
      error: "Finish or reassign CHG-0004 before deactivating Dana.",
    });
    expect(revalidatePath).not.toHaveBeenCalled();
  });

  it("returns ok and revalidates on success", async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce({});
    expect(await updateUser("u1", "Dana", { role: "quality" })).toEqual({ ok: true });
    expect(apiFetch).toHaveBeenCalledWith("/users/u1", {
      method: "PATCH",
      body: JSON.stringify({ role: "quality" }),
    });
    expect(revalidatePath).toHaveBeenCalledWith("/users");
  });
});

describe("inviteUser", () => {
  beforeEach(() => vi.clearAllMocks());

  it("posts the form fields", async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce({});
    const f = new FormData();
    f.set("email", "a@b.co");
    f.set("name", "A");
    f.set("role", "engineering");
    f.set("is_doc_manager", "on");
    expect(await inviteUser(f)).toEqual({ ok: true });
    expect(apiFetch).toHaveBeenCalledWith("/users", {
      method: "POST",
      body: JSON.stringify({
        email: "a@b.co",
        name: "A",
        role: "engineering",
        is_doc_manager: true,
      }),
    });
  });
});
