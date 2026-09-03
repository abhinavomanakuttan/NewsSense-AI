import { cn, formatDate, formatScore, formatTimeAgo } from "@/lib/utils";

describe("cn", () => {
  it("merges class names and handles conflicts", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
    expect(cn("text-red-500", "text-blue-500")).toBe("text-blue-500");
    expect(cn("flex", "items-center")).toBe("flex items-center");
  });

  it("filters out falsy values", () => {
    expect(cn("flex", false, undefined, null, "gap-2")).toBe("flex gap-2");
  });
});

describe("formatDate", () => {
  it("formats a valid ISO date", () => {
    expect(formatDate("2026-07-15T10:30:00Z")).toBe("Jul 15, 2026");
  });

  it("returns empty string for null/undefined", () => {
    expect(formatDate(null)).toBe("");
    expect(formatDate(undefined)).toBe("");
  });

  it("returns empty string for invalid dates", () => {
    expect(formatDate("not-a-date")).toBe("");
  });
});

describe("formatTimeAgo", () => {
  it("returns 'just now' for recent timestamps", () => {
    expect(formatTimeAgo(new Date().toISOString())).toBe("just now");
  });

  it("handles null and invalid input", () => {
    expect(formatTimeAgo(null)).toBe("");
    expect(formatTimeAgo(undefined)).toBe("");
    expect(formatTimeAgo("garbage")).toBe("");
  });
});

describe("formatScore", () => {
  it("formats a decimal score as a percentage", () => {
    expect(formatScore(0.87)).toBe("87%");
  });

  it("handles null and undefined", () => {
    expect(formatScore(null)).toBe("");
    expect(formatScore(undefined)).toBe("");
  });
});
