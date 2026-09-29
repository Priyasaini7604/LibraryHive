export type UserRole = "owner" | "student";

export interface User {
  id: string;
  name: string;
  email: string;
  phone?: string;
  role: UserRole;
  domain?: string;
  created_at?: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user?: User;
}

export type SeatStatus = "empty" | "reserved" | "occupied";

export interface Seat {
  id: string;
  library?: string;
  label: string;
  status: SeatStatus;
  created_at?: string;
  updated_at?: string;
}

export interface PricingPlan {
  id?: string;
  name: string;
  duration_days: number;
  price: number | string;
  created_at?: string;
}

export interface SeatSummary {
  total: number;
  empty: number;
  reserved: number;
  occupied: number;
}

export interface Library {
  id: string;
  owner_id?: string;
  owner_name?: string;
  name: string;
  address: string;
  latitude: number;
  longitude: number;
  contact_phone?: string;
  contact_email?: string;
  total_seats: number;
  opens_at?: string;
  closes_at?: string;
  operating_hours?: string;
  domains_catered?: string;
  domains?: string[];
  plans?: PricingPlan[];
  seat_summary?: SeatSummary;
  created_at?: string;
  updated_at?: string;
}

export interface LibraryCreateInput {
  name: string;
  address: string;
  latitude?: number;
  longitude?: number;
  contact_phone?: string;
  contact_email?: string;
  total_seats?: number;
  opens_at?: string;
  closes_at?: string;
  operating_hours?: string;
  domains_catered?: string | string[];
  pricing_plans?: Array<{
    name: string;
    duration_days: number;
    price: number;
  }>;
  initial_seats?: Array<{
    label: string;
    status?: SeatStatus;
  }>;
  seat_layout?: {
    rows: string[];
    seats_per_row: number;
  };
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error: string | null;
}
export type BookingStatus =
  | "reserved"
  | "confirmed"
  | "cancelled"
  | "expired";

export interface Booking {
  id: string;
  student: string;
  library: string;
  seat: string;
  plan: string;
  status: BookingStatus;
  reserved_until: string;
  created_at?: string;
  updated_at?: string;
}

export type PaymentMethod = "razorpay" | "cash" | "upi";

export type PaymentStatus = "pending" | "successful" | "failed";

export interface Payment {
  id: string;
  student: string;
  booking: string;
  amount: number | string;
  payment_method: PaymentMethod;
  status: PaymentStatus;
  razorpay_order_id?: string | null;
  razorpay_payment_id?: string | null;
  razorpay_signature?: string | null;
  transaction_id?: string | null;
  paid_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

export type MembershipStatus =
  | "active"
  | "due"
  | "overdue"
  | "archived";

export interface Membership {
  id: string;
  student: string;
  library: string;
  plan: string;
  seat: string;
  start_date: string;
  next_due_date: string;
  status: MembershipStatus;
  created_at?: string;
  updated_at?: string;
}