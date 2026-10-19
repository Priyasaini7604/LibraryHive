import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  deletePhoto,
  fetchLibraries,
  fetchOwnerLibrary,
  mediaUrl,
  setPlanActive,
  uploadPhoto,
} from "@/lib/api/libraries";
import { tokenStore } from "@/lib/auth";
import { ApiError } from "@/lib/errors";

function respond(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const ok = (data: unknown) => respond({ success: true, data, error: null, error_code: null, details: null, request_id: "r" });
const fail = (status: number, code: string) =>
  respond({ success: false, data: null, error: "x", error_code: code, details: null, request_id: "r" }, status);

describe("libraries api", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    tokenStore.clear();
  });
  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("sends discovery filters as repeatable query parameters without a token", async () => {
    tokenStore.set("secret-token");
    fetchMock.mockResolvedValue(ok({ items: [], page: 1, page_size: 12, total: 0 }));
    await fetchLibraries({ search: "hive", domain: "upsc", amenity: ["wifi", "ac"], lat: 25.4, lng: 81.8, page: 2 });
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    const parsed = new URL(String(url));
    expect(parsed.pathname).toBe("/api/v1/libraries/");
    expect(parsed.searchParams.getAll("amenity")).toEqual(["wifi", "ac"]);
    expect(parsed.searchParams.get("search")).toBe("hive");
    expect(parsed.searchParams.get("page")).toBe("2");
    expect((init?.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("returns null for an owner without a library and rethrows other errors", async () => {
    fetchMock.mockResolvedValueOnce(fail(409, "LIBRARY_REQUIRED"));
    await expect(fetchOwnerLibrary()).resolves.toBeNull();
    fetchMock.mockResolvedValueOnce(fail(500, "SERVER_ERROR"));
    await expect(fetchOwnerLibrary()).rejects.toBeInstanceOf(ApiError);
  });

  it("uploads photos as multipart form data", async () => {
    tokenStore.set("owner-token");
    fetchMock.mockResolvedValue(ok({ id: "p1" }));
    await uploadPhoto(new File(["x"], "a.jpg", { type: "image/jpeg" }), "Hall");
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toContain("/owner/library/photos/");
    expect(init?.body).toBeInstanceOf(FormData);
    const body = init?.body as FormData;
    expect((body.get("image") as File).name).toBe("a.jpg");
    expect(body.get("caption")).toBe("Hall");
    const headers = init?.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBeUndefined();
    expect(headers.Authorization).toBe("Bearer owner-token");
  });

  it("calls the activate, deactivate and delete endpoints", async () => {
    fetchMock.mockImplementation(async () => ok({}));
    await setPlanActive("plan1", false);
    await setPlanActive("plan1", true);
    await deletePhoto("photo1");
    const calls = fetchMock.mock.calls.map(([url, init]) => `${init?.method} ${new URL(String(url)).pathname}`);
    expect(calls).toEqual([
      "POST /api/v1/owner/library/plans/plan1/deactivate/",
      "POST /api/v1/owner/library/plans/plan1/activate/",
      "DELETE /api/v1/owner/library/photos/photo1/",
    ]);
  });

  it("makes relative media URLs absolute and leaves absolute ones alone", () => {
    expect(mediaUrl("/media/public/libraries/a.webp")).toBe("http://127.0.0.1:8000/media/public/libraries/a.webp");
    expect(mediaUrl("https://cdn.example.com/a.webp")).toBe("https://cdn.example.com/a.webp");
  });
});
