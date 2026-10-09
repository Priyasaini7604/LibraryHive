/**
 * The only place that formats money, dates and phones (UI_ARCHITECTURE.md 2.1).
 * Times are always shown in Asia/Kolkata, whatever the device time zone.
 */

export const BUSINESS_TIME_ZONE = "Asia/Kolkata";

const moneyFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
  minimumFractionDigits: 0,
});

/** "1200.00" -> "₹1,200"; "1200.50" -> "₹1,200.50" (paise shown only when present). */
export function formatMoney(amount: string | number): string {
  const value = typeof amount === "string" ? Number(amount) : amount;
  if (!Number.isFinite(value)) return "—";
  return Number.isInteger(value)
    ? moneyFormatter.format(value)
    : new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2 }).format(value);
}

const dateFormatter = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: BUSINESS_TIME_ZONE,
});

const dateTimeFormatter = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZone: BUSINESS_TIME_ZONE,
});

/** Business date "YYYY-MM-DD" (already in IST) -> "9 Oct 2026". */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  if (!year || !month || !day) return isoDate;
  // Noon UTC keeps the calendar day stable when formatted in IST.
  return dateFormatter.format(new Date(Date.UTC(year, month - 1, day, 12)));
}

/** UTC datetime -> "9 Oct 2026, 3:05 pm" in IST. */
export function formatDateTime(isoDateTime: string): string {
  const date = new Date(isoDateTime);
  return Number.isNaN(date.getTime()) ? isoDateTime : dateTimeFormatter.format(date);
}

/** Days between two business dates: "in 3 days", "today", "2 days overdue". */
export function relativeDue(dueDate: string, today: string): string {
  const days = Math.round((Date.parse(`${dueDate}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / 86_400_000);
  if (Number.isNaN(days)) return "";
  if (days === 0) return "due today";
  if (days === 1) return "due tomorrow";
  if (days > 1) return `due in ${days} days`;
  return days === -1 ? "1 day overdue" : `${-days} days overdue`;
}

/** "+919876543210" -> "+91 98765 43210"; other formats are returned unchanged. */
export function formatPhone(e164: string): string {
  const match = /^\+91(\d{5})(\d{5})$/.exec(e164);
  return match ? `+91 ${match[1]} ${match[2]}` : e164;
}
