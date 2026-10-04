import {
  ApiResponse,
  Library,
  LibraryCreateInput,
  Seat,
  SeatStatus,
  User,
  LoginResponse,
  DomainCount,
} from "./types";
import { authStorage } from "./auth";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

// Ensure URL does not end with trailing slash for clean concatenation
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

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
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

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await response.json() : null;

  if (!response.ok) {
    const errorMsg =
      data?.error ||
      data?.detail ||
      (typeof data === "string" ? data : JSON.stringify(data)) ||
      `Request failed with status ${response.status}`;
    throw new ApiError(errorMsg, response.status, data);
  }

  // If response follows { success: true, data: T }, return data.data, otherwise return full data
  if (data && typeof data === "object" && "success" in data && "data" in data) {
    return data.data as T;
  }

  return data as T;
}

export const apiClient = {
  // Authentication
  async login(credentials: { email: string; password: string }): Promise<LoginResponse> {
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
    // Fetch profile
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

  // Libraries (Person 1)
  async getLibraries(params?: {
    search?: string;
    domain?: string;
    lat?: number;
    lng?: number;
    radius?: number;
  }): Promise<Library[]> {
    const query = new URLSearchParams();
    if (params?.search) query.append("search", params.search);
    if (params?.domain) query.append("domain", params.domain);
    if (params?.lat !== undefined) query.append("lat", String(params.lat));
    if (params?.lng !== undefined) query.append("lng", String(params.lng));
    if (params?.radius !== undefined) query.append("radius", String(params.radius));

    const qs = query.toString();
    return request<Library[]>(`/libraries/${qs ? `?${qs}` : ""}`);
  },

  async getLibrary(id: string): Promise<Library> {
    return request<Library>(`/libraries/${id}/`);
  },

  async getMyLibrary(): Promise<Library> {
    return request<Library>("/libraries/me/");
  },

  async createLibrary(input: LibraryCreateInput): Promise<Library> {
    return request<Library>("/libraries/", {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  async updateLibrary(id: string, input: Partial<LibraryCreateInput>): Promise<Library> {
    return request<Library>(`/libraries/${id}/`, {
      method: "PATCH",
      body: JSON.stringify(input),
    });
  },

  // Seats (Person 1 setup integration & Person 2)
  async getLibrarySeats(libraryId: string): Promise<Seat[]> {
    return request<Seat[]>(`/libraries/${libraryId}/seats/`);
  },

  async addLibrarySeats(
    libraryId: string,
    payload:
      | Array<{ label: string; status?: SeatStatus }>
      | { rows: string[]; seats_per_row: number }
      | { seats: Array<{ label: string; status?: SeatStatus }> }
  ): Promise<Seat[]> {
    return request<Seat[]>(`/libraries/${libraryId}/seats/`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async updateSeatStatus(seatId: string, status: SeatStatus): Promise<Seat> {
    return request<Seat>(`/seats/${seatId}/`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  },

  async getSeat(seatId: string): Promise<Seat> {
    return request<Seat>(`/seats/${seatId}/`);
  },

  async getDomainBreakdown(libraryId: string): Promise<DomainCount[]> {
    return request<DomainCount[]>(`/libraries/${libraryId}/domain-breakdown/`);
  },
};
