import type { Granularity, TrendPoint } from "@/lib/platform-types";

const LABEL: Record<Granularity, string> = { day: "Daily", week: "Weekly (from Monday)", month: "Monthly" };

function shortDate(iso: string, granularity: Granularity): string {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1));
  const options: Intl.DateTimeFormatOptions =
    granularity === "month"
      ? { month: "short", year: "2-digit", timeZone: "UTC" }
      : { day: "numeric", month: "short", timeZone: "UTC" };
  return new Intl.DateTimeFormat("en-IN", options).format(date);
}

/**
 * Bookings per period as bars. Drawn with SVG (no chart dependency); the same numbers are in a screen-reader
 * table, and every bar has a text label via <title>, so the chart never relies on colour alone.
 */
export function TrendChart({ points, granularity }: { points: TrendPoint[]; granularity: Granularity }) {
  const max = Math.max(1, ...points.map((point) => point.bookings));
  const width = Math.max(320, points.length * 14);
  const height = 160;
  const barWidth = width / Math.max(points.length, 1);
  const first = points[0];
  const last = points[points.length - 1];
  return (
    <figure className="flex flex-col gap-2">
      <div className="overflow-x-auto">
        <svg
          role="img"
          aria-label={`${LABEL[granularity]} bookings, highest ${max}`}
          viewBox={`0 0 ${width} ${height + 4}`}
          className="h-48 w-full min-w-[320px]"
          preserveAspectRatio="none"
        >
          {points.map((point, index) => {
            const barHeight = (point.bookings / max) * height;
            return (
              <rect
                key={point.date}
                x={index * barWidth + barWidth * 0.15}
                y={height - barHeight}
                width={barWidth * 0.7}
                height={Math.max(barHeight, point.bookings > 0 ? 2 : 0)}
                rx={2}
                className="fill-blue-600"
              >
                <title>{`${shortDate(point.date, granularity)}: ${point.bookings} bookings, ${point.unique_students} students`}</title>
              </rect>
            );
          })}
          <line x1={0} x2={width} y1={height} y2={height} className="stroke-slate-300" strokeWidth={1} />
        </svg>
      </div>
      <figcaption className="flex justify-between text-xs text-slate-600">
        <span>{first ? shortDate(first.date, granularity) : ""}</span>
        <span>
          {LABEL[granularity]} · peak {max}
        </span>
        <span>{last ? shortDate(last.date, granularity) : ""}</span>
      </figcaption>
      <table className="sr-only">
        <caption>Bookings per period</caption>
        <thead>
          <tr>
            <th scope="col">Period</th>
            <th scope="col">Bookings</th>
            <th scope="col">Unique students</th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.date}>
              <th scope="row">{shortDate(point.date, granularity)}</th>
              <td>{point.bookings}</td>
              <td>{point.unique_students}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
