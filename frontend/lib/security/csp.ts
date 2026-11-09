import { tileOrigin } from "@/lib/map-config";

/**
 * Content-Security-Policy builder (SECURITY.md section 8).
 *
 * Scripts are allowed only with the per-request nonce ('strict-dynamic' lets
 * nonce'd scripts load their dependencies, e.g. Razorpay Checkout in T18).
 * Exact Razorpay domains are re-confirmed against Razorpay's documentation in
 * T18 before payments go live.
 */

export interface CspOptions {
  nonce: string;
  apiUrl: string;
  mediaOrigin?: string;
  /** Tile template of a non-default map provider (`NEXT_PUBLIC_MAP_TILE_URL`); its origin is allowed for images. */
  mapTileUrl?: string;
  isDev: boolean;
}

function originOf(url: string | undefined): string | null {
  if (!url) return null;
  try {
    return new URL(url).origin;
  } catch {
    return null;
  }
}

export function buildCsp({ nonce, apiUrl, mediaOrigin, mapTileUrl, isDev }: CspOptions): string {
  const api = originOf(apiUrl);
  // MEDIA_ORIGIN may list several origins, comma separated (the public photo store and the private bucket).
  const media = (mediaOrigin ?? "")
    .split(",")
    .map((origin) => originOf(origin.trim()))
    .filter((origin): origin is string => origin !== null);
  // Only a template that passes the same validation the map uses may add a source; anything else adds nothing.
  const tiles = tileOrigin(mapTileUrl);
  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    "script-src": [
      "'self'",
      `'nonce-${nonce}'`,
      "'strict-dynamic'",
      "https://checkout.razorpay.com",
      ...(isDev ? ["'unsafe-eval'"] : []),
    ],
    // Tailwind output is a stylesheet; Radix and Leaflet set inline styles at runtime.
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": [
      "'self'",
      "data:",
      "blob:",
      ...media,
      // Private payment images come from the API itself in development (signed links) and from the private
      // bucket in production (pre-signed URLs), so the API origin may serve images too.
      ...(api ? [api] : []),
      // OpenStreetMap now serves tiles from the bare host; the wildcard covers the older a/b/c subdomains.
      "https://tile.openstreetmap.org",
      "https://*.tile.openstreetmap.org",
      ...(tiles ? [tiles] : []),
    ],
    "font-src": ["'self'"],
    "connect-src": [
      "'self'",
      ...(api ? [api] : []),
      "https://api.razorpay.com",
      "https://nominatim.openstreetmap.org",
    ],
    "frame-src": ["https://api.razorpay.com", "https://checkout.razorpay.com"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
  };
  const policy = Object.entries(directives).map(([name, values]) => `${name} ${[...new Set(values)].join(" ")}`);
  if (!isDev) policy.push("upgrade-insecure-requests");
  return policy.join("; ");
}
