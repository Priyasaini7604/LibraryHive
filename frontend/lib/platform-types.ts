/** Internal platform analytics (GET /platform/analytics/*). Aggregates only; LibraryHive team access. */

export type Granularity = "day" | "week" | "month";

export interface DateRange {
  from: string;
  to: string;
}

export interface PlatformOverview {
  as_of: string;
  students: { registered: number; offline_walk_ins: number };
  libraries: { registered: number; published: number; active: number };
  bookings: { total: number; online: number; offline: number; unique_students: number; monthly_active_students: number };
}

export interface TrendPoint {
  date: string;
  bookings: number;
  unique_students: number;
}

export interface LibraryShare {
  library_id: string;
  name: string;
  bookings: number;
  unique_students: number;
}

export interface BookingAnalytics {
  range: DateRange;
  granularity: Granularity;
  today: number;
  this_week: number;
  this_month: number;
  in_range: {
    bookings: number;
    online: number;
    offline: number;
    unique_students: number;
    repeat_students: number;
    repeat_booking_percent: number | null;
    renewals: number;
    archived_memberships: number;
    check_ins: number;
    students_checked_in: number;
  };
  holds: {
    completed: number;
    cancelled: number;
    expired: number;
    still_pending: number;
    /** Holds whose student sent a direct UPI payment claim that the owner has not decided yet. Not abandoned. */
    awaiting_upi_review?: number;
    abandoned: number;
    abandoned_percent: number | null;
  };
  trend: TrendPoint[];
  by_library: LibraryShare[];
}

export interface PlatformLibraryRow {
  id: string;
  name: string;
  city: string;
  is_published: boolean;
  registered_members: number;
  active_members: number;
  online_students: number;
  total_bookings: number;
  bookings_in_range: number;
  unique_students_in_range: number;
  check_ins_in_range: number;
  subscription_plan: string | null;
  subscription_status: string | null;
}

export interface UnavailableMetric {
  key: string;
  label: string;
  reason: string;
}

export interface SubscriptionAnalytics {
  range: DateRange;
  libraries: number;
  averages_per_library: { bookings: number | null; unique_booking_students: number | null };
  platform_unique_students: number;
  student_payments_online: {
    successful: number;
    failed: number;
    cancelled: number;
    pending: number;
    needs_refund: number;
    /** Decimal string. Student fees paid to libraries: not LibraryHive revenue. */
    amount_successful: string;
    is_platform_revenue: false;
  };
  unavailable: UnavailableMetric[];
}

export type LibraryOrdering =
  | "bookings"
  | "total_bookings"
  | "members"
  | "active_members"
  | "online_students"
  | "check_ins"
  | "name";
