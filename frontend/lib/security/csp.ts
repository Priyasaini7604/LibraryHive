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

export function buildCsp({ nonce, apiUrl, mediaOrigin, isDev }: CspOptions): string {
  const api = originOf(apiUrl);
  const media = originOf(mediaOrigin);
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
    "img-src": ["'self'", "data:", "blob:", ...(media ? [media] : []), "https://*.tile.openstreetmap.org"],
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
