import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LocationPicker } from "@/components/library/location-picker";
import { buildCsp } from "@/lib/security/csp";
import { GeocodeError, parseNominatim, resetGeocoder } from "@/lib/geocode";
import { DEFAULT_ATTRIBUTION, DEFAULT_TILE_URL, isValidTileUrl, resolveMapConfig, tileOrigin } from "@/lib/map-config";

const mocks = vi.hoisted(() => ({ searchPlaces: vi.fn() }));

vi.mock("@/lib/geocode", async (original) => ({
  ...(await original<typeof import("@/lib/geocode")>()),
  searchPlaces: mocks.searchPlaces,
}));
vi.mock("@/components/library/library-map", () => ({
  LazyMap: ({ label, point }: { label: string; point: { latitude: number; longitude: number } | null }) => (
    <div role="region" aria-label={label} data-point={point ? `${point.latitude},${point.longitude}` : "none"} />
  ),
}));

describe("map configuration", () => {
  it("defaults to OpenStreetMap with its attribution", () => {
    const config = resolveMapConfig(undefined, undefined);
    expect(config.tileUrl).toBe(DEFAULT_TILE_URL);
    expect(config.attribution).toBe(DEFAULT_ATTRIBUTION);
    expect(config.attribution).toContain("OpenStreetMap");
  });

  it("accepts a custom https tile template and its own credit line", () => {
    const config = resolveMapConfig("https://tiles.example.com/{z}/{x}/{y}.png", "© Example, © OpenStreetMap contributors");
    expect(config).toEqual({ tileUrl: "https://tiles.example.com/{z}/{x}/{y}.png", attribution: "© Example, © OpenStreetMap contributors" });
  });

  it("keeps the OpenStreetMap credit when a custom provider gives none", () => {
    expect(resolveMapConfig("https://tiles.example.com/{z}/{x}/{y}.png", "   ").attribution).toBe(DEFAULT_ATTRIBUTION);
  });

  it("ignores tile templates that are not https or miss a placeholder", () => {
    for (const bad of ["http://tiles.example.com/{z}/{x}/{y}.png", "https://tiles.example.com/map.png", "javascript:alert(1)", "", "not a url"]) {
      expect(isValidTileUrl(bad), bad).toBe(false);
      expect(resolveMapConfig(bad, "x").tileUrl).toBe(DEFAULT_TILE_URL);
    }
    expect(isValidTileUrl("https://{s}.tiles.example.com/{z}/{x}/{y}.png")).toBe(true);
  });
});

describe("custom tile URL validation", () => {
  const good = "https://tiles.example.com/styles/{z}/{x}/{y}.png";

  it("accepts an https template and reduces it to its origin", () => {
    expect(tileOrigin(good)).toBe("https://tiles.example.com");
    expect(tileOrigin("https://tiles.example.com:8443/{z}/{x}/{y}.png?key=abc")).toBe("https://tiles.example.com:8443");
    expect(tileOrigin(DEFAULT_TILE_URL)).toBe("https://tile.openstreetmap.org");
  });

  it("turns the {s} subdomain placeholder into a wildcard source, and only when it leads the host", () => {
    expect(tileOrigin("https://{s}.tiles.example.com/{z}/{x}/{y}.png")).toBe("https://*.tiles.example.com");
    expect(tileOrigin("https://tiles.{s}.example.com/{z}/{x}/{y}.png")).toBeNull();
    expect(tileOrigin("https://tiles.example.com/{s}/{z}/{x}/{y}.png")).toBe("https://tiles.example.com");
  });

  it.each([
    ["plain http", "http://tiles.example.com/{z}/{x}/{y}.png"],
    ["protocol-relative", "//tiles.example.com/{z}/{x}/{y}.png"],
    ["javascript scheme", "javascript:alert(1)//{z}{x}{y}"],
    ["data scheme", "data:text/html,{z}{x}{y}"],
    ["credentials", "https://user:pass@tiles.example.com/{z}/{x}/{y}.png"],
    ["a missing {z}", "https://tiles.example.com/{x}/{y}.png"],
    ["a missing {x}", "https://tiles.example.com/{z}/{y}.png"],
    ["a missing {y}", "https://tiles.example.com/{z}/{x}.png"],
    ["an unknown placeholder", "https://tiles.example.com/{z}/{x}/{y}/{foo}.png"],
    ["a placeholder in the host", "https://{x}.example.com/{z}/{x}/{y}.png"],
    ["whitespace inside", "https://tiles.example.com/a b/{z}/{x}/{y}.png"],
    ["surrounding whitespace", " https://tiles.example.com/{z}/{x}/{y}.png"],
    ["a quote (CSP injection)", "https://tiles.example.com/{z}/{x}/{y}.png'"],
    ["a semicolon (CSP injection)", "https://tiles.example.com;script-src */{z}/{x}/{y}.png"],
    ["a comma", "https://tiles.example.com,https://evil.example/{z}/{x}/{y}.png"],
    ["a backslash", "https://tiles.example.com\\evil/{z}/{x}/{y}.png"],
    ["an empty host", "https:///{z}/{x}/{y}.png"],
    ["an empty string", ""],
  ])("rejects %s", (_name, value) => {
    expect(tileOrigin(value), value).toBeNull();
    expect(isValidTileUrl(value), value).toBe(false);
    expect(resolveMapConfig(value, "x").tileUrl).toBe(DEFAULT_TILE_URL);
  });

  it("treats undefined like an unset variable", () => {
    expect(tileOrigin(undefined)).toBeNull();
    expect(resolveMapConfig(undefined, undefined)).toEqual({ tileUrl: DEFAULT_TILE_URL, attribution: DEFAULT_ATTRIBUTION });
  });

  it("an invalid template never replaces the OpenStreetMap credit line either", () => {
    expect(resolveMapConfig("http://tiles.example.com/{z}/{x}/{y}.png", "© Someone Else").attribution).toBe(DEFAULT_ATTRIBUTION);
  });
});

describe("Content-Security-Policy for maps", () => {
  const base = { nonce: "n", apiUrl: "https://api.example.com/api/v1", isDev: false };

  it("allows OpenStreetMap tiles on the bare host and its subdomains by default", () => {
    const csp = buildCsp(base);
    expect(csp).toContain("https://tile.openstreetmap.org");
    expect(csp).toContain("https://*.tile.openstreetmap.org");
  });

  it("adds only the origin of a custom tile provider to img-src", () => {
    const csp = buildCsp({ ...base, mapTileUrl: "https://tiles.example.com/styles/{z}/{x}/{y}.png" });
    const img = csp.split("; ").find((part) => part.startsWith("img-src")) ?? "";
    expect(img).toContain("https://tiles.example.com");
    expect(img).not.toContain("/styles");
    expect(csp.split("; ").find((part) => part.startsWith("script-src"))).not.toContain("tiles.example.com");
  });

  it("adds a wildcard source for a {s} subdomain template", () => {
    const img = buildCsp({ ...base, mapTileUrl: "https://{s}.tiles.example.com/{z}/{x}/{y}.png" }).split("; ").find((part) => part.startsWith("img-src")) ?? "";
    expect(img).toContain("https://*.tiles.example.com");
  });

  it.each([
    "http://tiles.example.com/{z}/{x}/{y}.png",
    "https://user:pass@tiles.example.com/{z}/{x}/{y}.png",
    "https://tiles.example.com;script-src */{z}/{x}/{y}.png",
    "https://tiles.example.com/{z}/{x}.png",
    "javascript:alert(1)",
  ])("adds nothing to the policy for the invalid template %s", (bad) => {
    expect(buildCsp({ ...base, mapTileUrl: bad })).toBe(buildCsp(base));
  });

  it("never lets a tile template widen scripts, connections or frames", () => {
    const withTiles = buildCsp({ ...base, mapTileUrl: "https://tiles.example.com/{z}/{x}/{y}.png" }).split("; ");
    const without = buildCsp(base).split("; ");
    const changed = withTiles.filter((directive) => !without.includes(directive)).map((directive) => directive.split(" ")[0]);
    expect(changed).toEqual(["img-src"]);
  });

  it("allows Nominatim for connect-src and nothing else new", () => {
    expect(buildCsp(base)).toContain("https://nominatim.openstreetmap.org");
  });
});

describe("geocoding (Nominatim)", () => {
  const row = { place_id: 1, display_name: "Civil Lines, Prayagraj, India", lat: "25.4358", lon: "81.8463" };
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    resetGeocoder();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [row] });
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  // The component tests mock `searchPlaces`; here the real one is needed.
  const real = async () => (await vi.importActual<typeof import("@/lib/geocode")>("@/lib/geocode")).searchPlaces;

  it("sends one India-restricted request with no cookies and parses the places", async () => {
    const search = await real();
    const places = await search("  Civil   Lines ");
    expect(places).toEqual([{ id: "1", name: "Civil Lines, Prayagraj, India", latitude: 25.4358, longitude: 81.8463 }]);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("https://nominatim.openstreetmap.org/search?");
    expect(url).toContain("countrycodes=in");
    expect(url).toContain("limit=5");
    expect(url).toContain("q=civil+lines");
    expect(init.credentials).toBe("omit");
  });

  it("does not search for fewer than three characters (nothing is sent)", async () => {
    const search = await real();
    await expect(search("ab")).resolves.toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("answers a repeated search from memory without a second request", async () => {
    const search = await real();
    await search("Civil Lines");
    await search("civil  lines");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("spaces different searches at least a second apart", async () => {
    const search = await real();
    const started: number[] = [];
    fetchMock.mockImplementation(async () => {
      started.push(Date.now());
      return { ok: true, json: async () => [row] };
    });
    const first = search("Civil Lines");
    const second = search("Allahabad Junction");
    await vi.advanceTimersByTimeAsync(3000);
    await Promise.all([first, second]);
    expect(started).toHaveLength(2);
    expect((started[1] ?? 0) - (started[0] ?? 0)).toBeGreaterThanOrEqual(1000);
  });

  it("turns a server error or a network failure into a friendly error", async () => {
    const search = await real();
    fetchMock.mockResolvedValueOnce({ ok: false, status: 429, json: async () => ({}) });
    await expect(search("Civil Lines")).rejects.toBeInstanceOf(GeocodeError);
    resetGeocoder();
    fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    await expect(search("Civil Lines")).rejects.toThrow(/unavailable/i);
  });

  it("drops malformed rows and impossible coordinates", () => {
    expect(
      parseNominatim([
        row,
        { display_name: "No coordinates" },
        { display_name: "Bad", lat: "95", lon: "10" },
        { display_name: "Worse", lat: "abc", lon: "10" },
        null,
      ]),
    ).toHaveLength(1);
    expect(parseNominatim({ not: "an array" })).toEqual([]);
  });
});

describe("LocationPicker", () => {
  beforeEach(() => mocks.searchPlaces.mockReset());

  it("searches only when the button is pressed, never while typing", async () => {
    mocks.searchPlaces.mockResolvedValue([]);
    render(<LocationPicker latitude="" longitude="" onChange={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("Search for a place"), "Civil Lines");
    expect(mocks.searchPlaces).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /find on map/i }));
    expect(mocks.searchPlaces).toHaveBeenCalledWith("Civil Lines");
  });

  it("Enter searches and does not submit the surrounding profile form", async () => {
    mocks.searchPlaces.mockResolvedValue([]);
    const submit = vi.fn((event: React.FormEvent) => event.preventDefault());
    render(
      <form onSubmit={submit}>
        <LocationPicker latitude="" longitude="" onChange={vi.fn()} />
      </form>,
    );
    await userEvent.type(screen.getByLabelText("Search for a place"), "Civil Lines{Enter}");
    expect(mocks.searchPlaces).toHaveBeenCalledTimes(1);
    expect(submit).not.toHaveBeenCalled();
  });

  it("picking a result fills the coordinates with six decimals", async () => {
    mocks.searchPlaces.mockResolvedValue([{ id: "1", name: "Civil Lines, Prayagraj", latitude: 25.4358, longitude: 81.8463 }]);
    const onChange = vi.fn();
    render(<LocationPicker latitude="" longitude="" onChange={onChange} />);
    await userEvent.type(screen.getByLabelText("Search for a place"), "Civil Lines");
    await userEvent.click(screen.getByRole("button", { name: /find on map/i }));
    const results = await screen.findByRole("list", { name: "Search results" });
    await userEvent.click(within(results).getByRole("button", { name: "Civil Lines, Prayagraj" }));
    expect(onChange).toHaveBeenCalledWith("25.435800", "81.846300");
  });

  it("explains short queries, empty results and failures", async () => {
    render(<LocationPicker latitude="" longitude="" onChange={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("Search for a place"), "ab");
    await userEvent.click(screen.getByRole("button", { name: /find on map/i }));
    expect(await screen.findByText(/at least 3 letters/i)).toBeInTheDocument();
    expect(mocks.searchPlaces).not.toHaveBeenCalled();

    mocks.searchPlaces.mockResolvedValueOnce([]);
    await userEvent.type(screen.getByLabelText("Search for a place"), "c");
    await userEvent.click(screen.getByRole("button", { name: /find on map/i }));
    expect(await screen.findByText(/no place found/i)).toBeInTheDocument();

    mocks.searchPlaces.mockRejectedValueOnce(new GeocodeError());
    await userEvent.click(screen.getByRole("button", { name: /find on map/i }));
    expect(await screen.findByText(/unavailable right now/i)).toBeInTheDocument();
  });

  it("tells the owner what is sent, and passes the typed coordinates to the map", () => {
    render(<LocationPicker latitude="25.4358" longitude="81.8463" onChange={vi.fn()} />);
    expect(screen.getByText(/sent to OpenStreetMap's search service/i)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /placing your library's pin/i })).toHaveAttribute("data-point", "25.4358,81.8463");
  });

  it("ignores invalid typed coordinates instead of drawing a pin", () => {
    render(<LocationPicker latitude="95" longitude="10" onChange={vi.fn()} />);
    expect(screen.getByRole("region", { name: /placing your library's pin/i })).toHaveAttribute("data-point", "none");
  });
});

describe("real Leaflet map", () => {
  it("shows the OpenStreetMap attribution and a pin for the library", async () => {
    const { default: LeafletMap } = await vi.importActual<typeof import("@/components/library/leaflet-map")>("@/components/library/leaflet-map");
    render(<LeafletMap label="Map showing where Silent Hive is" point={{ latitude: 25.4358, longitude: 81.8463 }} />);
    expect(screen.getByRole("region", { name: "Map showing where Silent Hive is" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("link", { name: "OpenStreetMap" })).toHaveAttribute("href", "https://www.openstreetmap.org/copyright"));
    expect(screen.getByText(/contributors/)).toBeInTheDocument();
  });
});

describe("touch scrolling on the display-only map", () => {
  const original = window.matchMedia;
  const coarse = (matches: boolean) => {
    window.matchMedia = ((query: string) => ({ matches: matches && query.includes("coarse"), media: query }) as MediaQueryList) as typeof window.matchMedia;
  };
  afterEach(() => {
    window.matchMedia = original;
  });

  const draggable = async (props: { onPick?: () => void }) => {
    const { default: LeafletMap } = await vi.importActual<typeof import("@/components/library/leaflet-map")>("@/components/library/leaflet-map");
    const { container } = render(<LeafletMap label="Map" point={{ latitude: 25.4358, longitude: 81.8463 }} {...props} />);
    return container.querySelector(".leaflet-container")?.classList.contains("leaflet-grab") ?? false;
  };

  it("does not capture one-finger drags on a phone, so the page can scroll", async () => {
    coarse(true);
    expect(await draggable({})).toBe(false);
  });

  it("keeps drag-to-pan with a mouse or trackpad", async () => {
    coarse(false);
    expect(await draggable({})).toBe(true);
  });

  it("keeps panning on a phone for the owner's location picker", async () => {
    coarse(true);
    expect(await draggable({ onPick: vi.fn() })).toBe(true);
  });

  it("still shows the zoom buttons and the attribution when dragging is off", async () => {
    coarse(true);
    await draggable({});
    expect(screen.getByRole("button", { name: "Zoom in" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "OpenStreetMap" })).toBeInTheDocument();
  });

  it("treats a browser without matchMedia as a mouse", async () => {
    // @ts-expect-error simulating an environment without matchMedia
    window.matchMedia = undefined;
    expect(await draggable({})).toBe(true);
  });
});
