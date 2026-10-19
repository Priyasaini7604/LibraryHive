import { Badge, type Tone } from "./surface";

import type {
  ComplaintCategory,
  ComplaintStatus,
  MembershipStatus,
  PaymentMethod,
  PaymentStatus,
  VisitSlot,
  VisitStatus,
} from "@/lib/types";

/** Every status is shown as words, never as colour alone (UI_ARCHITECTURE.md 8). */

const MEMBERSHIP: Record<MembershipStatus, [Tone, string]> = {
  active: ["success", "Active"],
  due: ["warning", "Due soon"],
  overdue: ["danger", "Overdue"],
  archived: ["neutral", "Ended"],
};

export function MembershipBadge({ status }: { status: MembershipStatus }) {
  const [tone, label] = MEMBERSHIP[status];
  return <Badge tone={tone}>{label}</Badge>;
}

const PAYMENT: Record<PaymentStatus, [Tone, string]> = {
  success: ["success", "Paid"],
  pending: ["warning", "Pending"],
  failed: ["danger", "Failed"],
  cancelled: ["neutral", "Cancelled"],
  needs_refund: ["danger", "Refund due"],
};

export function PaymentBadge({ status }: { status: PaymentStatus }) {
  const [tone, label] = PAYMENT[status];
  return <Badge tone={tone}>{label}</Badge>;
}

export const METHOD_LABEL: Record<PaymentMethod, string> = {
  gateway: "Online",
  cash: "Cash",
  upi_direct: "UPI (direct)",
  bank_transfer: "Bank transfer",
};

const COMPLAINT: Record<ComplaintStatus, [Tone, string]> = {
  open: ["warning", "Open"],
  in_progress: ["info", "In progress"],
  resolved: ["success", "Resolved"],
};

export function ComplaintBadge({ status }: { status: ComplaintStatus }) {
  const [tone, label] = COMPLAINT[status];
  return <Badge tone={tone}>{label}</Badge>;
}

export const CATEGORY_LABEL: Record<ComplaintCategory, string> = {
  noise: "Noise",
  ac: "Air conditioning",
  wifi: "Wi-Fi",
  cleanliness: "Cleanliness",
  power_lighting: "Power and lighting",
  seat_furniture: "Seat and furniture",
  staff: "Staff",
  other: "Other",
};

const VISIT: Record<VisitStatus, [Tone, string]> = {
  pending: ["warning", "Waiting for the library"],
  accepted: ["success", "Accepted"],
  rejected: ["danger", "Declined"],
  cancelled: ["neutral", "Cancelled"],
};

export function VisitBadge({ status }: { status: VisitStatus }) {
  const [tone, label] = VISIT[status];
  return <Badge tone={tone}>{label}</Badge>;
}

export const SLOT_LABEL: Record<VisitSlot, string> = {
  morning: "Morning",
  afternoon: "Afternoon",
  evening: "Evening",
};
