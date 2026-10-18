import { describe, expect, it } from "vitest";

import {
  claimCompleteSchema,
  loginSchema,
  passwordSchema,
  phoneSchema,
  profileSchema,
  registerSchema,
  resetPasswordSchema,
} from "@/lib/schemas/auth";

describe("phoneSchema", () => {
  it.each(["98765 43210", "+91-98765-43210", "09876543210", "919876543210", " 9876543210 "])("accepts %s", (value) => {
    expect(phoneSchema.safeParse(value).success).toBe(true);
  });

  it.each(["", "12345", "5876543210", "+14155552671", "98765 4321x"])("rejects %j", (value) => {
    expect(phoneSchema.safeParse(value).success).toBe(false);
  });
});

describe("passwordSchema", () => {
  it("needs 8 characters that are not only digits", () => {
    expect(passwordSchema.safeParse("Str0ng-pass").success).toBe(true);
    expect(passwordSchema.safeParse("short1").success).toBe(false);
    expect(passwordSchema.safeParse("12345678").success).toBe(false);
  });
});

describe("form schemas", () => {
  it("login trims the email and needs a password", () => {
    const parsed = loginSchema.safeParse({ email: "  asha@example.com ", password: "x" });
    expect(parsed.success && parsed.data.email).toBe("asha@example.com");
    expect(loginSchema.safeParse({ email: "nope", password: "x" }).success).toBe(false);
    expect(loginSchema.safeParse({ email: "a@b.co", password: "" }).success).toBe(false);
  });

  it("register accepts both roles and rejects others", () => {
    const base = { name: "Asha Rao", email: "asha@example.com", phone: "9876543210", password: "Str0ng-pass" };
    expect(registerSchema.safeParse({ ...base, role: "owner" }).success).toBe(true);
    expect(registerSchema.safeParse({ ...base, role: "student", domain_code: "neet" }).success).toBe(true);
    expect(registerSchema.safeParse({ ...base, role: "admin" }).success).toBe(false);
  });

  it("claim code accepts a 6-digit OTP and an owner code with hyphen or spaces", () => {
    const base = { password: "Str0ng-pass" };
    for (const code of ["123456", "ABCD-2345", "abcd 2345"]) {
      expect(claimCompleteSchema.safeParse({ ...base, code }).success).toBe(true);
    }
    expect(claimCompleteSchema.safeParse({ ...base, code: "12" }).success).toBe(false);
    expect(claimCompleteSchema.safeParse({ ...base, code: "12<script>" }).success).toBe(false);
  });

  it("reset requires a 6-digit code and matching passwords", () => {
    const ok = { email: "a@b.co", code: "123456", new_password: "Str0ng-pass", confirm_password: "Str0ng-pass" };
    expect(resetPasswordSchema.safeParse(ok).success).toBe(true);
    const mismatch = resetPasswordSchema.safeParse({ ...ok, confirm_password: "other-pass1" });
    expect(mismatch.success).toBe(false);
    expect(!mismatch.success && mismatch.error.issues[0]?.path).toEqual(["confirm_password"]);
    expect(resetPasswordSchema.safeParse({ ...ok, code: "12345" }).success).toBe(false);
  });

  it("profile needs a name and a valid phone", () => {
    expect(profileSchema.safeParse({ name: "Asha", phone: "9876543210" }).success).toBe(true);
    expect(profileSchema.safeParse({ name: "A", phone: "9876543210" }).success).toBe(false);
    expect(profileSchema.safeParse({ name: "Asha", phone: "123" }).success).toBe(false);
  });
});
