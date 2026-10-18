import { z } from "zod";

/** Mirrors BACKEND_ARCHITECTURE.md #53 and #54; the server stays the source of truth for identity and seats. */

const PHONE = /^(\+?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}$/;

export const admissionSchema = z.object({
  name: z.string().trim().min(2, "Enter the student's name.").max(120, "Use at most 120 characters."),
  phone: z.string().trim().regex(PHONE, "Enter a valid Indian mobile number."),
  email: z
    .string()
    .trim()
    .refine((value) => value === "" || z.email().safeParse(value).success, "Enter a valid email address."),
  domain_code: z.string(),
  seat_id: z.string().min(1, "Choose a seat."),
  plan_id: z.string().min(1, "Choose a plan."),
  start_date: z.string(),
  method: z.enum(["cash", "upi_direct", "bank_transfer"]),
  notes: z.string().trim().max(500, "Use at most 500 characters."),
});

export type AdmissionValues = z.infer<typeof admissionSchema>;
