"use client";

import { Search } from "lucide-react";
import { useState } from "react";

import { LazyMap } from "@/components/library/library-map";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/surface";
import { type Place, searchPlaces } from "@/lib/geocode";

type SearchState =
  | { kind: "idle" }
  | { kind: "searching" }
  | { kind: "results"; places: Place[] }
  | { kind: "empty" }
  | { kind: "error"; message: string };

function toPoint(latitude: string, longitude: string) {
  const lat = Number(latitude);
  const lng = Number(longitude);
  const valid = latitude.trim() !== "" && longitude.trim() !== "" && Math.abs(lat) <= 90 && Math.abs(lng) <= 180;
  return valid && Number.isFinite(lat) && Number.isFinite(lng) ? { latitude: lat, longitude: lng } : null;
}

/**
 * The owner sets the library's pin: search for a place, then click the map or drag the pin. The latitude and
 * longitude fields stay as the fallback and the source of truth. The place search runs only when the owner presses
 * the button or Enter (never while typing), and it is rate-limited and cached in `lib/geocode.ts`.
 */
export function LocationPicker({
  latitude,
  longitude,
  onChange,
}: {
  latitude: string;
  longitude: string;
  onChange: (latitude: string, longitude: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState<SearchState>({ kind: "idle" });

  const set = (lat: number, lng: number) => onChange(lat.toFixed(6), lng.toFixed(6));

  async function search() {
    if (query.trim().length < 3) {
      setState({ kind: "error", message: "Type at least 3 letters of an area, street or landmark." });
      return;
    }
    setState({ kind: "searching" });
    try {
      const places = await searchPlaces(query);
      setState(places.length === 0 ? { kind: "empty" } : { kind: "results", places });
    } catch (error) {
      setState({ kind: "error", message: error instanceof Error ? error.message : "The place search failed." });
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          aria-label="Search for a place"
          placeholder="Search an area, street or landmark"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault(); // this sits inside the profile form: Enter must search, not save
              void search();
            }
          }}
        />
        <Button variant="secondary" loading={state.kind === "searching"} onClick={() => void search()}>
          <Search aria-hidden="true" className="size-4" /> Find on map
        </Button>
      </div>
      <p className="text-sm text-slate-600">
        The text you search for is sent to OpenStreetMap&apos;s search service (Nominatim) together with your IP address. It is sent only when you press the button.
      </p>

      <div role="status" aria-live="polite">
        {state.kind === "empty" && <Alert tone="info">No place found. Try a larger area or enter the coordinates by hand.</Alert>}
        {state.kind === "error" && <Alert tone="warning">{state.message}</Alert>}
      </div>
      {state.kind === "results" && (
        <ul aria-label="Search results" className="flex flex-col gap-1">
          {state.places.map((place) => (
            <li key={place.id}>
              <button
                type="button"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-left text-sm text-slate-800 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
                onClick={() => {
                  set(place.latitude, place.longitude);
                  setState({ kind: "idle" });
                }}
              >
                {place.name}
              </button>
            </li>
          ))}
        </ul>
      )}

      <LazyMap
        label="Map for placing your library's pin"
        point={toPoint(latitude, longitude)}
        onPick={(point) => set(point.latitude, point.longitude)}
      />
      <p className="text-sm text-slate-600">Click the map or drag the pin to place it exactly. You can also type the coordinates below.</p>
    </div>
  );
}
