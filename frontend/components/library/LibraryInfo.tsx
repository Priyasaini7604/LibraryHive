import React from "react";
import { MapPin, Phone, Mail, Clock, User, ExternalLink } from "lucide-react";
import { Library } from "@/lib/types";

interface LibraryInfoProps {
  library: Library;
}

const cardStyle: React.CSSProperties = {
  background: "#ffffff",
  border: "1px solid #e2e8f0",
  borderRadius: "12px",
  padding: "22px",
  boxShadow: "0 2px 10px rgba(15, 23, 42, 0.04)",
};

const rowStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  gap: "10px",
  fontSize: "14px",
  color: "#334155",
};

const mutedStyle: React.CSSProperties = { color: "#94a3b8" };

/** "08:30:00" -> "8:30 AM". Returns "" when the value is missing/invalid. */
const formatTime = (value?: string | null): string => {
  if (!value) return "";
  const [h, m] = value.split(":");
  const hours = Number(h);
  const minutes = Number(m);
  if (Number.isNaN(hours) || Number.isNaN(minutes)) return "";
  const suffix = hours >= 12 ? "PM" : "AM";
  const hour12 = hours % 12 === 0 ? 12 : hours % 12;
  return `${hour12}:${String(minutes).padStart(2, "0")} ${suffix}`;
};

const getTimings = (library: Library): string => {
  if (library.operating_hours && library.operating_hours.trim()) {
    return library.operating_hours.trim();
  }
  const opens = formatTime(library.opens_at);
  const closes = formatTime(library.closes_at);
  if (opens && closes) return `${opens} - ${closes}`;
  return "";
};

// Coordinates default to 0,0 on the backend when the owner never set them.
const getMapsUrl = (library: Library): string | null => {
  const { latitude, longitude } = library;
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  if (latitude === 0 && longitude === 0) return null;
  return `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`;
};

export default function LibraryInfo({ library }: LibraryInfoProps) {
  const timings = getTimings(library);
  const mapsUrl = getMapsUrl(library);
  const domains = library.domains || [];

  return (
    <section style={cardStyle}>
      <h2
        style={{
          fontSize: "13px",
          fontWeight: 700,
          color: "#64748b",
          letterSpacing: "0.05em",
          textTransform: "uppercase",
          margin: 0,
        }}
      >
        About this library
      </h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(min(260px, 100%), 1fr))",
          gap: "16px 28px",
          marginTop: "16px",
        }}
      >
        <div style={rowStyle}>
          <MapPin size={17} color="#475569" style={{ flexShrink: 0, marginTop: "2px" }} />
          <div>
            <div>{library.address}</div>
            {mapsUrl && (
              <a
                href={mapsUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                  marginTop: "6px",
                  fontSize: "13px",
                  fontWeight: 600,
                  color: "#2563eb",
                }}
              >
                Open in Maps <ExternalLink size={13} />
              </a>
            )}
          </div>
        </div>

        <div style={rowStyle}>
          <Clock size={17} color="#475569" style={{ flexShrink: 0, marginTop: "2px" }} />
          {timings ? (
            <span>{timings}</span>
          ) : (
            <span style={mutedStyle}>Timings not listed</span>
          )}
        </div>

        <div style={rowStyle}>
          <Phone size={17} color="#475569" style={{ flexShrink: 0, marginTop: "2px" }} />
          {library.contact_phone ? (
            <a href={`tel:${library.contact_phone}`} style={{ color: "#334155" }}>
              {library.contact_phone}
            </a>
          ) : (
            <span style={mutedStyle}>Phone not listed</span>
          )}
        </div>

        <div style={rowStyle}>
          <Mail size={17} color="#475569" style={{ flexShrink: 0, marginTop: "2px" }} />
          {library.contact_email ? (
            <a
              href={`mailto:${library.contact_email}`}
              style={{ color: "#334155", wordBreak: "break-all" }}
            >
              {library.contact_email}
            </a>
          ) : (
            <span style={mutedStyle}>Email not listed</span>
          )}
        </div>

        {library.owner_name && (
          <div style={rowStyle}>
            <User size={17} color="#475569" style={{ flexShrink: 0, marginTop: "2px" }} />
            <span>Managed by {library.owner_name}</span>
          </div>
        )}
      </div>

      <div style={{ marginTop: "20px" }}>
        <div style={{ fontSize: "13px", fontWeight: 600, color: "#64748b" }}>
          Domains served
        </div>
        {domains.length > 0 ? (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "8px",
              marginTop: "8px",
            }}
          >
            {domains.map((domain) => (
              <span
                key={domain}
                style={{
                  background: "#eff6ff",
                  color: "#1d4ed8",
                  border: "1px solid #bfdbfe",
                  borderRadius: "999px",
                  padding: "3px 12px",
                  fontSize: "13px",
                  fontWeight: 600,
                }}
              >
                {domain}
              </span>
            ))}
          </div>
        ) : (
          <div style={{ ...mutedStyle, fontSize: "14px", marginTop: "6px" }}>
            Not listed
          </div>
        )}
      </div>
    </section>
  );
}
