import { describe, expect, it, vi } from "vitest";

vi.mock("next-auth", () => ({
  default: () => ({ handlers: {}, auth: vi.fn(), signIn: vi.fn(), signOut: vi.fn() }),
}));
vi.mock("next-auth/providers/google", () => ({ default: {} }));

import { authConfig } from "@/auth";

describe("session callback", () => {
  it("never exposes the id token", async () => {
    const session = await authConfig.callbacks!.session!({
      session: { user: {}, expires: "" },
      token: {
        id_token: "secret",
        refresh_token: "r",
        user: {
          id: "u1",
          email: "a@example.com",
          name: "A",
          role: "other",
          is_doc_manager: true,
          deactivated: false,
        },
      },
    } as never);
    expect(session).not.toHaveProperty("idToken");
    expect(JSON.stringify(session)).not.toContain("secret");
    expect(session.user).toMatchObject({ id: "u1", isDocManager: true });
  });
});
