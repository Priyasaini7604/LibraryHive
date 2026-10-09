/**
 * API errors and the friendly messages shown for each error code
 * (BACKEND_ARCHITECTURE.md 6.1, UI_ARCHITECTURE.md 10.3).
 */

export type FieldErrors = Record<string, string[]>;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: FieldErrors | null;
  readonly requestId: string | null;

  constructor(options: {
    status: number;
    code: string;
    message: string;
    details?: FieldErrors | null;
    requestId?: string | null;
  }) {
    super(options.message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details ?? null;
    this.requestId = options.requestId ?? null;
  }
}

/** Raised when the request never reached the server (offline, DNS, CORS). */
export const NETWORK_ERROR = "NETWORK_ERROR";

const FRIENDLY_MESSAGES: Record<string, string> = {
  NETWORK_ERROR: "We couldn't reach the server. Check your connection and try again.",
  VALIDATION_ERROR: "Please correct the highlighted fields.",
  INVALID_CREDENTIALS: "Email or password is incorrect.",
  NOT_AUTHENTICATED: "Please log in to continue.",
  TOKEN_INVALID: "Your session has expired. Please log in again.",
  FORBIDDEN_ROLE: "You don't have access to this page.",
  NOT_FOUND: "We couldn't find what you were looking for.",
  LIBRARY_REQUIRED: "Finish setting up your library first.",
  LIBRARY_EXISTS: "You already have a library.",
  EMAIL_TAKEN: "An account with this email already exists.",
  PHONE_TAKEN: "An account with this phone number already exists.",
  CLAIM_REQUIRED: "A library already added you as a member. Verify it's you to link your account.",
  IDENTITY_CONFLICT: "This phone number and email belong to different accounts. Please check the details.",
  CLAIM_INVALID: "That code is wrong or has expired.",
  RESET_INVALID: "That code is wrong or has expired.",
  CLAIM_LOCKED: "Too many attempts. Please wait a few minutes and try again.",
  LIBRARY_NOT_BOOKABLE: "This library isn't taking bookings right now.",
  PLAN_INACTIVE: "This plan is no longer available. Please choose another.",
  SEAT_UNAVAILABLE: "That seat was just taken. Please pick another.",
  HOLD_EXISTS: "You already have a seat on hold at this library.",
  ALREADY_MEMBER: "You already have a seat at this library.",
  HOLD_EXPIRED: "Your seat hold expired.",
  SEAT_IN_USE: "This seat has an active member or hold. Archive or release it first.",
  PLAN_NAME_TAKEN: "You already have an active plan with this name.",
  PHOTO_LIMIT: "You've reached the maximum number of photos.",
  FILE_TOO_LARGE: "This file is too large.",
  FILE_TYPE: "Upload a JPG, PNG or WEBP image.",
  INVALID_SIGNATURE:
    "We couldn't verify this payment. If money was deducted it will be sorted out automatically; check My payments in a few minutes.",
  PAYMENT_NOT_PENDING: "This payment has already been completed or cancelled.",
  SEAT_LOST_REFUND_PENDING:
    "Your payment was received but the seat was no longer available. The library will refund you.",
  RENEWAL_NOT_OPEN: "Renewal opens 7 days before your due date.",
  MEMBERSHIP_ARCHIVED: "This membership has ended.",
  ALREADY_CHECKED_IN: "You're already checked in.",
  NOT_CHECKED_IN: "You're not checked in.",
  NO_ACTIVE_MEMBERSHIP: "You need an active membership at this library.",
  INVALID_TRANSITION: "This change isn't allowed in the current status.",
  VISIT_PENDING_EXISTS: "You already have a pending visit request for this library.",
  RATE_LIMITED: "Too many attempts. Please wait a few minutes and try again.",
  GATEWAY_ERROR: "Payments are temporarily unavailable. Please try again shortly.",
  METHOD_NOT_ALLOWED: "This action isn't available.",
  UNSUPPORTED_MEDIA_TYPE: "This request couldn't be processed.",
  PARSE_ERROR: "This request couldn't be processed.",
  SERVICE_UNAVAILABLE: "The service is temporarily unavailable. Please try again shortly.",
  ORIGIN_NOT_ALLOWED: "This request was blocked for your security. Please reload the page and try again.",
  SERVER_ERROR: "Something went wrong on our side.",
};

const GENERIC_MESSAGE = "Something went wrong on our side.";

/** The message to show a user for any thrown value. */
export function userMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const friendly = FRIENDLY_MESSAGES[error.code] ?? GENERIC_MESSAGE;
    const isUnexpected = !(error.code in FRIENDLY_MESSAGES) || error.code === "SERVER_ERROR";
    return isUnexpected && error.requestId ? `${friendly} Reference: ${error.requestId}` : friendly;
  }
  return GENERIC_MESSAGE;
}

export function isApiError(error: unknown, code?: string): error is ApiError {
  return error instanceof ApiError && (code === undefined || error.code === code);
}
