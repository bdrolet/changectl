import { describe, expect, it } from "vitest";

import { latestApprovalByUser } from "@/lib/approvals";
import type { ApprovalOut } from "@/lib/types";

function row(over: Partial<ApprovalOut>): ApprovalOut {
  return {
    id: "x",
    user_id: "u1",
    name: "Una",
    email: "u1@example.com",
    decision: "approved",
    comment: null,
    signed_at: "2026-10-01T10:00:00Z",
    voided_at: null,
    voided_reason: null,
    ...over,
  };
}

describe("latestApprovalByUser", () => {
  it("keeps the newest row per user, whatever the input order", () => {
    const old = row({ id: "a", signed_at: "2026-10-01T10:00:00Z" });
    const newer = row({
      id: "b",
      decision: "changes_requested",
      comment: "fix torque",
      signed_at: "2026-10-02T10:00:00Z",
    });
    const other = row({ id: "c", user_id: "u2" });
    const latest = latestApprovalByUser([old, other, newer]);
    expect(latest.get("u1")?.id).toBe("b");
    expect(latest.get("u1")?.comment).toBe("fix torque");
    expect(latest.get("u2")?.id).toBe("c");
    expect(latest.has("u3")).toBe(false);
  });
});
