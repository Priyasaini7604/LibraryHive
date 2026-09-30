import {
  ApiResponse,
  Library,
  LibraryCreateInput,
  Seat,
  SeatStatus,
  User,
  LoginResponse,
  Booking,
  Payment,
  Membership,
  Notification,
} from "./types";

import { authStorage } from "./auth";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000/api/v1";

const API_BASE = BASE_URL.replace(/\/+$/, "");

class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

// ---------------------------------------------------------
// Refresh access token
// ---------------------------------------------------------

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = authStorage.getRefreshToken();

  if (!refreshToken) {
    return null;
  }

  try {
    const response = await fetch(`${API_BASE}/auth/refresh/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        refresh: refreshToken,
      }),
    });

    if (!response.ok) {
      authStorage.clear();
      return null;
    }

    const data = await response.json();

    if (!data.access) {
      authStorage.clear();
      return null;
    }

    authStorage.setAccessToken(data.access);

    return data.access;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------
// API request helper
// ---------------------------------------------------------

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  isRetry = false
): Promise<T> {
  const token = authStorage.getAccessToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const url = `${API_BASE}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers,
  });

  const isJson = response.headers
    .get("content-type")
    ?.includes("application/json");

  const data = isJson ? await response.json() : null;

  // -------------------------------------------------------
  // Access token expired/invalid
  // -------------------------------------------------------

  if (response.status === 401 && !isRetry) {
    const newAccessToken = await refreshAccessToken();

    if (newAccessToken) {
      return request<T>(endpoint, options, true);
    }
  }

  if (!response.ok) {
    const errorMsg =
      data?.error ||
      data?.detail ||
      (typeof data === "string"
        ? data
        : JSON.stringify(data)) ||
      `Request failed with status ${response.status}`;

    throw new ApiError(errorMsg, response.status, data);
  }

  // If response follows { success: true, data: T }
  if (
    data &&
    typeof data === "object" &&
    "success" in data &&
    "data" in data
  ) {
    return data.data as T;
  }

  return data as T;
}

export const apiClient = {
  // =========================================================
  // Authentication
  // =========================================================

  async login(
    credentials: { email: string; password: string }
  ): Promise<LoginResponse> {
    const res = await request<LoginResponse>("/auth/login/", {
      method: "POST",
      body: JSON.stringify(credentials),
    });

    if (res.access) {
      authStorage.setAccessToken(res.access);

      if (res.refresh) {
        authStorage.setRefreshToken(res.refresh);
      }
    }

    try {
      const user = await this.getMe();

      authStorage.setUser(user);

      return { ...res, user };
    } catch {
      return res;
    }
  },

  async register(payload: {
    name: string;
    email: string;
    password: string;
    phone?: string;
    role: "owner" | "student";
    domain?: string;
  }): Promise<User> {
    return request<User>("/auth/register/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async getMe(): Promise<User> {
    return request<User>("/auth/me/");
  },

  logout() {
    authStorage.clear();
  },

  // =========================================================
  // Libraries
  // =========================================================

  async getLibraries(params?: {
    search?: string;
    domain?: string;
    lat?: number;
    lng?: number;
    radius?: number;
  }): Promise<Library[]> {
    const query = new URLSearchParams();

    if (params?.search) {
      query.append("search", params.search);
    }

    if (params?.domain) {
      query.append("domain", params.domain);
    }

    if (params?.lat !== undefined) {
      query.append("lat", String(params.lat));
    }

    if (params?.lng !== undefined) {
      query.append("lng", String(params.lng));
    }

    if (params?.radius !== undefined) {
      query.append("radius", String(params.radius));
    }

    const qs = query.toString();

    return request<Library[]>(
      `/libraries/${qs ? `?${qs}` : ""}`
    );
  },

  async getLibrary(id: string): Promise<Library> {
    return request<Library>(`/libraries/${id}/`);
  },

  async getMyLibrary(): Promise<Library> {
    return request<Library>("/libraries/me/");
  },

  async createLibrary(
    input: LibraryCreateInput
  ): Promise<Library> {
    return request<Library>("/libraries/", {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  async updateLibrary(
    id: string,
    input: Partial<LibraryCreateInput>
  ): Promise<Library> {
    return request<Library>(`/libraries/${id}/`, {
      method: "PATCH",
      body: JSON.stringify(input),
    });
  },

  // =========================================================
  // Seats
  // =========================================================

  async getLibrarySeats(libraryId: string): Promise<Seat[]> {
    return request<Seat[]>(
      `/libraries/${libraryId}/seats/`
    );
  },

  async addLibrarySeats(
    libraryId: string,
    payload:
      | Array<{ label: string; status?: SeatStatus }>
      | { rows: string[]; seats_per_row: number }
      | {
          seats: Array<{
            label: string;
            status?: SeatStatus;
          }>;
        }
  ): Promise<Seat[]> {
    return request<Seat[]>(
      `/libraries/${libraryId}/seats/`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  async updateSeatStatus(
    seatId: string,
    status: SeatStatus
  ): Promise<Seat> {
    return request<Seat>(`/seats/${seatId}/`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  },

  // =========================================================
  // Bookings
  // =========================================================

  async getBookings(): Promise<Booking[]> {
    return request<Booking[]>("/bookings/");
  },

  async createBooking(payload: {
    library: string;
    seat: string;
    plan: string;
  }): Promise<Booking> {
    return request<Booking>("/bookings/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // =========================================================
  // Payments
  // =========================================================

  async createPaymentOrder(bookingId: string): Promise<{
    order_id: string;
    amount: number | string;
    currency: string;
    key_id: string;
    booking_id: string;
    payment_id: string;
  }> {
    return request("/payments/create-order/", {
      method: "POST",
      body: JSON.stringify({
        booking: bookingId,
      }),
    });
  },

  async verifyPayment(payload: {
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
  }): Promise<{
    message: string;
    payment: Payment;
    booking_status: string;
    seat_status: string;
    membership_id: string;
    membership_status: string;
    next_due_date: string;
  }> {
    return request("/payments/verify/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // =========================================================
  // Memberships
  // =========================================================

  async getMemberships(): Promise<Membership[]> {
    return request<Membership[]>("/memberships/");
  },

  // =========================================================
  // Notifications
  // =========================================================

  async getNotifications(): Promise<Notification[]> {
    return request<Notification[]>("/notifications/");
  },

  async markNotificationAsRead(
    notificationId: string
  ): Promise<Notification> {
    return request<Notification>(
      `/notifications/${notificationId}/read/`,
      {
        method: "PATCH",
      }
    );
  },
};