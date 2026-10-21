"use client";

import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect } from "react";
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from "react-leaflet";

import { INDIA_CENTER, MAP_CONFIG, usesTouchAsPrimary } from "@/lib/map-config";

export interface MapPoint {
  latitude: number;
  longitude: number;
}

interface LeafletMapProps {
  /** Accessible name of the map region. */
  label: string;
  /** The library's position. Without one the map opens on India. */
  point: MapPoint | null;
  /** When given the pin can be placed by clicking the map or dragging the pin (the owner's location picker). */
  onPick?: (point: MapPoint) => void;
  className?: string;
}

const PIN_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="30" height="40" viewBox="0 0 30 40" aria-hidden="true">' +
  '<path d="M15 1C7.3 1 1 7.2 1 14.9 1 25.5 15 39 15 39s14-13.5 14-24.1C29 7.2 22.7 1 15 1z" fill="#2563eb" stroke="#ffffff" stroke-width="2"/>' +
  '<circle cx="15" cy="15" r="5.5" fill="#ffffff"/></svg>';

/** A pin drawn inline, so no marker image files have to be bundled or allowed by the CSP. This module only loads in the browser. */
const PIN_ICON = L.divIcon({ className: "", html: PIN_SVG, iconSize: [30, 40], iconAnchor: [15, 40] });

function FollowPoint({ point }: { point: MapPoint | null }) {
  const map = useMap();
  useEffect(() => {
    if (point) map.setView([point.latitude, point.longitude], Math.max(map.getZoom(), 15));
  }, [map, point]);
  return null;
}

function ClickToPick({ onPick }: { onPick: (point: MapPoint) => void }) {
  useMapEvents({
    click: (event) => onPick({ latitude: event.latlng.lat, longitude: event.latlng.lng }),
  });
  return null;
}

/**
 * One Leaflet map. Loaded lazily and only in the browser (see `library-map.tsx`). Tiles and the credit line come
 * from `MAP_CONFIG`, so the OpenStreetMap attribution is always visible in the corner of the map.
 */
export default function LeafletMap({ label, point, onPick, className }: LeafletMapProps) {
  const center: [number, number] = point ? [point.latitude, point.longitude] : INDIA_CENTER;
  // Only the owner's picker needs one-finger panning; a display-only map yields to page scrolling on phones.
  const allowDrag = Boolean(onPick) || !usesTouchAsPrimary();
  return (
    <div role="region" aria-label={label} className={className ?? "h-72 w-full overflow-hidden rounded-xl border border-slate-300"}>
      <MapContainer center={center} zoom={point ? 15 : 4} scrollWheelZoom={false} dragging={allowDrag} className="size-full" worldCopyJump>
        <TileLayer url={MAP_CONFIG.tileUrl} attribution={MAP_CONFIG.attribution} maxZoom={19} />
        {point && (
          <Marker
            position={[point.latitude, point.longitude]}
            icon={PIN_ICON}
            draggable={Boolean(onPick)}
            keyboard
            title={onPick ? "Library location. Drag it to move it, or click the map." : "Library location"}
            eventHandlers={
              onPick
                ? { dragend: (event) => onPick({ latitude: event.target.getLatLng().lat, longitude: event.target.getLatLng().lng }) }
                : undefined
            }
          />
        )}
        <FollowPoint point={point} />
        {onPick && <ClickToPick onPick={onPick} />}
      </MapContainer>
    </div>
  );
}
