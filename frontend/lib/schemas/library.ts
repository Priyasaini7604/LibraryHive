import { z } from "zod";

/** Mirrors the server rules of BACKEND_ARCHITECTURE.md #17 and #21; the server stays the source of truth. */

const text = (max: number) => z.string().trim().max(max, `Use at most ${max} characters.`);

export const libraryProfileSchema = z
  .object({
    name: z.string().trim().min(2, "Enter the library name.").max(150, "Use at most 150 characters."),
    description: text(2000),
    address: z.string().trim().min(3, "Enter the full address.").max(255, "Use at most 255 characters."),
    city: z.string().trim().min(2, "Enter the city.").max(80, "Use at most 80 characters."),
    area: text(80),
    contact_phone: z
      .string()
      .trim()
      .refine(
        (value) => value === "" || /^(\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}$/.test(value),
        "Enter a valid Indian mobile number.",
      ),
    contact_email: z
      .string()
      .trim()
      .refine((value) => value === "" || z.email().safeParse(value).success, "Enter a valid email address."),
    opens_at: z.string(),
    closes_at: z.string(),
    operating_notes: text(200),
    latitude: z
      .string()
      .trim()
      .refine(
        (value) => value === "" || (!Number.isNaN(Number(value)) && Math.abs(Number(value)) <= 90),
        "Latitude is between -90 and 90.",
      ),
    longitude: z
      .string()
      .trim()
      .refine(
        (value) => value === "" || (!Number.isNaN(Number(value)) && Math.abs(Number(value)) <= 180),
        "Longitude is between -180 and 180.",
      ),
    domain_codes: z.array(z.string()),
    amenity_codes: z.array(z.string()),
  })
  .refine((value) => (value.latitude === "") === (value.longitude === ""), {
    message: "Set latitude and longitude together or leave both empty.",
    path: ["latitude"],
  });

export type LibraryProfileValues = z.infer<typeof libraryProfileSchema>;

export const planSchema = z.object({
  name: z.string().trim().min(2, "Enter a plan name.").max(60, "Use at most 60 characters."),
  duration_days: z
    .string()
    .trim()
    .regex(/^\d+$/, "Enter a whole number of days.")
    .refine((value) => Number(value) >= 1 && Number(value) <= 366, "Duration is between 1 and 366 days."),
  price: z
    .string()
    .trim()
    .regex(/^\d+(\.\d{1,2})?$/, "Enter an amount like 1200 or 1200.50.")
    .refine((value) => Number(value) > 0, "The price must be more than zero."),
  timing_note: text(100),
});

export type PlanValues = z.infer<typeof planSchema>;
