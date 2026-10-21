/**
 * Place search through Nominatim (OpenStreetMap), approved provisionally under U2 / SEC-4.
 *
 * Privacy and policy rules this module enforces:
 * - It is called only from an explicit search submit, never while typing (no autocomplete).
 * - At most one request per second (Nominatim usage policy); calls are queued, never dropped or burst.
 * - The typed text and the visitor's IP go to nominatim.openstreetmap.org, which the Privacy Policy discloses.
 * - Results are cached in memory for the page's lifetime, so repeating a search sends nothing.
 *
 * This is a third-party service, so it does not go through `api-client.ts` (the lint rule exempts this file only).
 */

const ENDPOINT = "https://nominatim.openstreetmap.org/search";
const MIN_INTERVAL_MS = 1100;
const TIMEOUT_MS = 8000;
const CACHE_LIMIT = 50;

export interface Place {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
}

export class GeocodeError extends Error {
  constructor(message = "The place search is unavailable right now. Enter the coordinates by hand.") {
    super(message);
    this.name = "GeocodeError";
  }
}

interface NominatimRow {
  place_id?: number | string;
  display_name?: string;
  lat?: string;
  lon?: string;
}

const cache = new Map<string, Place[]>();
let lastRequestAt = 0;
let queue: Promise<unknown> = Promise.resolve();

/** For tests: forget the cache and the rate-limit clock. */
export function resetGeocoder(): void {
  cache.clear();
  lastRequestAt = 0;
  queue = Promise.resolve();
}

function normalise(query: string): string {
  return query.trim().replace(/\s+/g, " ").toLowerCase();
}

export function parseNominatim(rows: unknown): Place[] {
  if (!Array.isArray(rows)) return [];
  const places: Place[] = [];
  for (const row of rows as (NominatimRow | null)[]) {
    if (!row || typeof row !== "object") continue;
    const latitude = Number(row.lat);
    const longitude = Number(row.lon);
    if (!row.display_name || !Number.isFinite(latitude) || !Number.isFinite(longitude)) continue;
    if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180) continue;
    places.push({ id: String(row.place_id ?? `${latitude},${longitude}`), name: row.display_name, latitude, longitude });
  }
  return places;
}

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

async function request(query: string): Promise<Place[]> {
  const sinceLast = Date.now() - lastRequestAt;
  if (sinceLast < MIN_INTERVAL_MS) await wait(MIN_INTERVAL_MS - sinceLast);
  lastRequestAt = Date.now();

  const params = new URLSearchParams({ format: "jsonv2", q: query, countrycodes: "in", limit: "5" });
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${ENDPOINT}?${params}`, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
      credentials: "omit",
      referrerPolicy: "strict-origin-when-cross-origin",
    });
    if (!response.ok) throw new GeocodeError();
    return parseNominatim(await response.json());
  } catch (error) {
    throw error instanceof GeocodeError ? error : new GeocodeError();
  } finally {
    clearTimeout(timer);
  }
}

/** Search for a place name. Call this only from a submit handler. Resolves to at most five places. */
export function searchPlaces(query: string): Promise<Place[]> {
  const key = normalise(query);
  if (key.length < 3) return Promise.resolve([]);
  const cached = cache.get(key);
  if (cached) return Promise.resolve(cached);

  const run = queue.then(async () => {
    const again = cache.get(key); // a queued duplicate of a search that just finished
    if (again) return again;
    const places = await request(key);
    if (cache.size >= CACHE_LIMIT) cache.delete(cache.keys().next().value as string);
    cache.set(key, places);
    return places;
  });
  queue = run.catch(() => undefined);
  return run;
}
