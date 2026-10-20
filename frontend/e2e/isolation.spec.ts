import { expect, test } from "@playwright/test";

import { DEMO_OWNER_EMAIL, DEMO_PASSWORD, apiLogin, apiRegister, newAccount } from "./helpers";

/** Role checks and tenant isolation through the real HTTP stack (SECURITY.md sections 5 and 6). */
test.describe("access control and tenant isolation", () => {
  test("anonymous callers get 401 on private endpoints", async ({ request }) => {
    for (const path of ["student/memberships/", "owner/members/", "owner/dashboard/", "notifications/"]) {
      const response = await request.get(`http://127.0.0.1:8010/api/v1/${path}`);
      expect(response.status(), path).toBe(401);
    }
  });

  test("a student gets 403 on every owner endpoint", async () => {
    const student = newAccount("student");
    await apiRegister(student);
    const { api } = await apiLogin(student.email, student.password);
    for (const path of ["owner/members/", "owner/dashboard/", "owner/dues/", "owner/payments/", "owner/seats/"]) {
      const response = await api.get(`/api/v1/${path}`);
      expect(response.status(), path).toBe(403);
    }
    await api.dispose();
  });

  test("an owner gets 403 on student endpoints", async () => {
    const { api } = await apiLogin(DEMO_OWNER_EMAIL, DEMO_PASSWORD);
    for (const path of ["student/memberships/", "student/payments/"]) {
      const response = await api.get(`/api/v1/${path}`);
      expect(response.status(), path).toBe(403);
    }
    await api.dispose();
  });

  test("another library's owner cannot see or change a member: the id answers 404, not 403", async () => {
    const demo = await apiLogin(DEMO_OWNER_EMAIL, DEMO_PASSWORD);
    const members = await demo.api.get("/api/v1/owner/members/");
    expect(members.status()).toBe(200);
    const rows = ((await members.json()) as { data: { items: { membership_id: string }[] } }).data.items;
    expect(rows.length).toBeGreaterThan(0);
    const memberId = rows[0]?.membership_id ?? "";
    expect(memberId).toMatch(/^[0-9a-f-]{36}$/); // a real id, so a 404 below can only mean "not your tenant"

    const other = newAccount("owner", "rival");
    await apiRegister(other);
    const rival = await apiLogin(other.email, other.password);
    const created = await rival.api.post("/api/v1/owner/library/", {
      data: {
        name: `Rival Hall ${other.email.slice(6, 12)}`,
        address: "2 Rival Road",
        city: "Prayagraj",
        area: "Civil Lines",
        latitude: 25.44,
        longitude: 81.85,
        contact_phone: other.phone,
        contact_email: other.email,
        opens_at: "06:00",
        closes_at: "22:00",
        operating_notes: "",
        domain_codes: [],
        amenity_codes: [],
      },
    });
    expect(created.status(), await created.text()).toBe(201);

    // Valid bodies, so a 404 can only come from the tenant check and not from input validation.
    for (const [method, path, data] of [
      ["get", `owner/members/${memberId}/`, undefined],
      ["post", `owner/members/${memberId}/archive/`, { reason: "Not my member" }],
      ["post", `owner/members/${memberId}/renewals/`, { method: "cash" }],
    ] as const) {
      const response = await rival.api[method](`/api/v1/${path}`, data ? { data } : undefined);
      expect(response.status(), `${method} ${path}`).toBe(404);
    }
    // And nothing happened: the member is still active for its own owner.
    const still = await demo.api.get(`/api/v1/owner/members/${memberId}/`);
    expect(((await still.json()) as { data: { status: string } }).data.status).not.toBe("archived");

    // Control: the owner of that library gets the same member with 200, so the rival's 404 is about tenancy.
    expect((await demo.api.get(`/api/v1/owner/members/${memberId}/`)).status()).toBe(200);

    // The rival's own lists never contain the demo library's data.
    const own = await rival.api.get("/api/v1/owner/members/");
    expect(((await own.json()) as { data: { items: unknown[] } }).data.items).toEqual([]);
    await Promise.all([demo.api.dispose(), rival.api.dispose()]);
  });

  test("the public seat map and library page never reveal who sits where", async ({ request }) => {
    const list = await request.get("http://127.0.0.1:8010/api/v1/libraries/");
    const libraries = ((await list.json()) as { data: { items: { id: string; name: string }[] } }).data.items;
    const demo = libraries.find((library) => library.name === "Demo Study Hall");
    expect(demo).toBeDefined();
    const seats = await request.get(`http://127.0.0.1:8010/api/v1/libraries/${demo?.id}/seats/`);
    const text = await seats.text();
    expect(text).not.toMatch(/Aarav|Diya|Kabir|Meera|Rohan|Sana|98765000(0[1-9])/);
    const detail = await request.get(`http://127.0.0.1:8010/api/v1/libraries/${demo?.id}/`);
    expect(await detail.text()).not.toMatch(/Aarav|Diya|Kabir|Meera|Rohan|Sana|98765000(0[1-9])/);
  });
});
