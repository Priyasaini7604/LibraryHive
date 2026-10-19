import { describe, expect, it } from "vitest";

import { formatTime } from "@/lib/format";
import { libraryProfileSchema, planSchema } from "@/lib/schemas/library";

const profile = {
  name: "Silent Hive",
  description: "",
  address: "12 Civil Lines",
  city: "Prayagraj",
  area: "",
  contact_phone: "",
  contact_email: "",
  opens_at: "",
  closes_at: "",
  operating_notes: "",
  latitude: "",
  longitude: "",
  domain_codes: [],
  amenity_codes: [],
};

const messages = (values: object) => {
  const result = libraryProfileSchema.safeParse(values);
  return result.success ? [] : result.error.issues.map((issue) => `${issue.path.join(".")}: ${issue.message}`);
};

describe("libraryProfileSchema", () => {
  it("accepts a minimal profile", () => {
    expect(messages(profile)).toEqual([]);
  });

  it("requires name, address and city", () => {
    const issues = messages({ ...profile, name: "", address: " ", city: "" });
    expect(issues.some((m) => m.startsWith("name"))).toBe(true);
    expect(issues.some((m) => m.startsWith("address"))).toBe(true);
    expect(issues.some((m) => m.startsWith("city"))).toBe(true);
  });

  it("checks phone and email only when given", () => {
    expect(messages({ ...profile, contact_phone: "98765 43210", contact_email: "a@b.in" })).toEqual([]);
    expect(messages({ ...profile, contact_phone: "12345" })).toContain("contact_phone: Enter a valid Indian mobile number.");
    expect(messages({ ...profile, contact_email: "nope" })).toContain("contact_email: Enter a valid email address.");
  });

  it("keeps coordinates in range and paired", () => {
    expect(messages({ ...profile, latitude: "25.4", longitude: "81.8" })).toEqual([]);
    expect(messages({ ...profile, latitude: "91", longitude: "81" })).toContain("latitude: Latitude is between -90 and 90.");
    expect(messages({ ...profile, latitude: "10", longitude: "181" })).toContain("longitude: Longitude is between -180 and 180.");
    expect(messages({ ...profile, latitude: "10" })).toContain(
      "latitude: Set latitude and longitude together or leave both empty.",
    );
    expect(messages({ ...profile, latitude: "abc", longitude: "1" })).toContain("latitude: Latitude is between -90 and 90.");
  });
});

describe("planSchema", () => {
  const plan = { name: "Monthly", duration_days: "30", price: "1200", timing_note: "" };
  const issues = (values: object) => {
    const result = planSchema.safeParse(values);
    return result.success ? [] : result.error.issues.map((issue) => `${issue.path.join(".")}: ${issue.message}`);
  };

  it("accepts valid plans including paise and the 366-day limit", () => {
    expect(issues(plan)).toEqual([]);
    expect(issues({ ...plan, price: "1200.50", duration_days: "366" })).toEqual([]);
  });

  it("rejects bad durations and prices", () => {
    expect(issues({ ...plan, duration_days: "0" })).toContain("duration_days: Duration is between 1 and 366 days.");
    expect(issues({ ...plan, duration_days: "367" })).toContain("duration_days: Duration is between 1 and 366 days.");
    expect(issues({ ...plan, duration_days: "1.5" })).toContain("duration_days: Enter a whole number of days.");
    expect(issues({ ...plan, price: "0" })).toContain("price: The price must be more than zero.");
    expect(issues({ ...plan, price: "12.345" })).toContain("price: Enter an amount like 1200 or 1200.50.");
    expect(issues({ ...plan, price: "-5" })).toContain("price: Enter an amount like 1200 or 1200.50.");
    expect(issues({ ...plan, name: "" }).some((m) => m.startsWith("name"))).toBe(true);
  });
});

describe("formatTime", () => {
  it("formats 24-hour times for the 12-hour clock", () => {
    expect(formatTime("06:00:00")).toBe("6:00 am");
    expect(formatTime("22:30")).toBe("10:30 pm");
    expect(formatTime("00:05:00")).toBe("12:05 am");
    expect(formatTime("12:00:00")).toBe("12:00 pm");
    expect(formatTime(null)).toBe("");
    expect(formatTime("later")).toBe("");
  });
});
