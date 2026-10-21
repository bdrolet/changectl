import { vi } from "vitest";

// `server-only` throws outside the Next.js server bundler.
vi.mock("server-only", () => ({}));
