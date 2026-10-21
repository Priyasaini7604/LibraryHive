/**
 * Map tile configuration (UI_ARCHITECTURE.md U2, docs/MAP_TILE_PROVIDER_PROPOSAL.md).
 *
 * The pilot uses OpenStreetMap's own tile servers. The provider is switched with two environment variables, so
 * moving to a hosted or self-hosted provider later needs no code change (only a CSP origin, which `proxy.ts`
 * derives from the same variable). Attribution is never optional: OpenStreetMap data always needs credit.
 */

export const DEFAULT_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
export const DEFAULT_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors';

export interface MapConfig {
  tileUrl: string;
  attribution: string;
}

/**
 * Validate a custom tile template and return the origin the Content-Security-Policy may allow for it, or `null`.
 * The same check feeds the map (which template to load) and the CSP (which host to allow), so they cannot disagree.
 *
 * Accepted: an `https://` URL, with no credentials, whose path or query contains `{z}`, `{x}` and `{y}`, and whose
 * host is plain. `{s}` (Leaflet's subdomain placeholder) is accepted only as the left-most host label and becomes a
 * `*.` wildcard source. Rejected: other schemes, credentials, whitespace, quotes, separators, unknown placeholders
 * (`{foo}`), placeholders inside the host, and anything that does not parse as a URL.
 */
export function tileOrigin(value: string | undefined): string | null {
  if (!value || value !== value.trim()) return null;
  if (/[\s"'<>`\\;,]/.test(value)) return null; // whitespace, quotes, backslash and CSP separators
  if (!value.startsWith("https://")) return null;
  for (const required of ["{z}", "{x}", "{y}"]) if (!value.includes(required)) return null;
  if ((value.match(/\{[^}]*\}/g) ?? []).some((token) => !["{z}", "{x}", "{y}", "{s}"].includes(token))) return null;

  const authority = /^https:\/\/([^/?#]*)/.exec(value)?.[1] ?? "";
  const subdomainWildcard = authority.startsWith("{s}.");
  const plainAuthority = subdomainWildcard ? authority.slice(4) : authority;
  if (!plainAuthority || /[{}@]/.test(plainAuthority)) return null; // placeholders in the host, or credentials

  try {
    // The `{s}.` label is dropped for parsing: only the host that follows it is the CSP source.
    const url = new URL(`https://${plainAuthority}${value.slice(8 + authority.length)}`.replace(/\{[zxys]\}/g, "0"));
    if (url.protocol !== "https:" || url.username || url.password || !url.hostname) return null;
    return subdomainWildcard ? `https://*.${url.host}` : url.origin;
  } catch {
    return null;
  }
}

/** A usable tile template passes `tileOrigin`; anything else is ignored and the OpenStreetMap default is used. */
export function isValidTileUrl(value: string | undefined): value is string {
  return tileOrigin(value) !== null;
}

/** Pure so it can be tested; `MAP_CONFIG` below feeds it the build-time variables. */
export function resolveMapConfig(tileUrl?: string, attribution?: string): MapConfig {
  const customTiles = isValidTileUrl(tileUrl);
  return {
    tileUrl: customTiles ? tileUrl : DEFAULT_TILE_URL,
    // A custom provider brings its own credit line; without one the OpenStreetMap credit stays.
    attribution: customTiles && attribution?.trim() ? attribution : DEFAULT_ATTRIBUTION,
  };
}

// Literal `process.env.NEXT_PUBLIC_*` reads are what Next.js inlines into the browser bundle.
export const MAP_CONFIG: MapConfig = resolveMapConfig(
  process.env.NEXT_PUBLIC_MAP_TILE_URL,
  process.env.NEXT_PUBLIC_MAP_ATTRIBUTION,
);

/**
 * True when the main pointer is a finger. A map that only displays a place must not capture one-finger drags
 * there, or a thumb that lands on it cannot scroll the page. Pinch zoom, the zoom buttons and the "Open in maps"
 * link still work; with dragging off, Leaflet leaves `touch-action: pan-x pan-y` so the browser scrolls natively.
 */
export function usesTouchAsPrimary(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia("(pointer: coarse)").matches;
}

/** Where the map opens when a library has no coordinates yet (the middle of India). */
export const INDIA_CENTER: [number, number] = [22.9734, 78.6569];
