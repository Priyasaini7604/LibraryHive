"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { StatCard } from "@/components/charts/stat-card";
import { RangeFilter, useDateRange } from "@/components/platform/range-filter";
import { TrendChart } from "@/components/platform/trend-chart";
import { Button } from "@/components/ui/button";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Alert, Card, CardContent, CardHeader, CardTitle, ProgressBar } from "@/components/ui/surface";
import { fetchPlatformBookings, fetchPlatformOverview, fetchPlatformSubscriptions } from "@/lib/api/platform";
import { formatMoney } from "@/lib/format";
import type { DateRange, Granularity } from "@/lib/platform-types";
import { queryKeys } from "@/lib/query-keys";

const GRANULARITIES: { value: Granularity; label: string }[] = [
  { value: "day", label: "Daily" },
  { value: "week", label: "Weekly" },
  { value: "month", label: "Monthly" },
];

const percent = (value: number | null) => (value === null ? "n/a" : `${value}%`);
const average = (value: number | null) => (value === null ? "n/a" : String(value));

function Section({ id, title, hint, children }: { id: string; title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <div>
        <h2 id={id} className="text-lg font-semibold text-slate-900">
          {title}
        </h2>
        {hint && <p className="text-sm text-slate-600">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">{children}</div>;
}

function OverviewSection() {
  const query = useQuery({ queryKey: queryKeys.platformOverview, queryFn: fetchPlatformOverview });
  if (query.isPending) return <LoadingList label="Loading platform overview" rows={2} />;
  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We could not load the overview." />;
  }
  const { students, libraries, bookings } = query.data;
  return (
    <Grid>
      <StatCard label="Registered students" value={students.registered} hint={`Plus ${students.offline_walk_ins} walk-ins added by owners`} />
      <StatCard label="Registered libraries" value={libraries.registered} hint={`${libraries.published} published`} />
      <StatCard label="Active libraries" value={libraries.active} hint="At least one live membership now" />
      <StatCard label="Total seat bookings" value={bookings.total} hint={`${bookings.online} online · ${bookings.offline} added by owners`} />
      <StatCard label="Students who have booked" value={bookings.unique_students} hint="Distinct students with at least one booking" />
      <StatCard label="Monthly active students" value={bookings.monthly_active_students} hint="Booked in the current calendar month" />
    </Grid>
  );
}

function BookingsSection({
  range,
  granularity,
  onGranularity,
}: {
  range: DateRange;
  granularity: Granularity;
  onGranularity: (value: Granularity) => void;
}) {
  const valid = range.to >= range.from;
  const query = useQuery({
    queryKey: queryKeys.platformBookings({ ...range, granularity }),
    queryFn: () => fetchPlatformBookings(range, granularity),
    enabled: valid,
  });
  if (!valid) return null;
  if (query.isPending) return <LoadingList label="Loading booking analytics" rows={3} />;
  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We could not load booking analytics." />;
  }
  const data = query.data;
  const topMax = Math.max(1, ...data.by_library.map((row) => row.bookings));
  return (
    <div className="flex flex-col gap-4">
      <Grid>
        <StatCard label="Bookings today" value={data.today} />
        <StatCard label="Bookings this week" value={data.this_week} hint="Since Monday" />
        <StatCard label="Bookings this month" value={data.this_month} />
        <StatCard label="Bookings in range" value={data.in_range.bookings} hint={`${data.in_range.online} online · ${data.in_range.offline} added by owners`} />
        <StatCard label="Unique booking students" value={data.in_range.unique_students} hint="Each student counted once" />
        <StatCard
          label="Repeat booking rate"
          value={percent(data.in_range.repeat_booking_percent)}
          hint={`${data.in_range.repeat_students} of these students have booked more than once`}
        />
        <StatCard label="Renewals paid" value={data.in_range.renewals} hint="Successful renewal payments" />
        <StatCard label="Students who checked in" value={data.in_range.students_checked_in} hint={`${data.in_range.check_ins} check-ins`} />
        <StatCard
          label="Abandoned booking holds"
          value={data.holds.abandoned}
          hint={`${percent(data.holds.abandoned_percent)} of finished holds expired or were cancelled unpaid`}
          tone={data.holds.abandoned > 0 ? "warning" : "neutral"}
        />
      </Grid>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>Booking trend</CardTitle>
            <div role="group" aria-label="Trend period" className="flex gap-1">
              {GRANULARITIES.map((option) => (
                <Button
                  key={option.value}
                  size="sm"
                  variant={granularity === option.value ? "primary" : "secondary"}
                  aria-pressed={granularity === option.value}
                  onClick={() => onGranularity(option.value)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {data.in_range.bookings === 0 ? (
            <EmptyState title="No bookings in this range" description="Try a longer date range." />
          ) : (
            <TrendChart points={data.trend} granularity={data.granularity} />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Bookings by library (top 10)</CardTitle>
        </CardHeader>
        <CardContent>
          {data.by_library.length === 0 ? (
            <EmptyState title="No bookings in this range" />
          ) : (
            <ul aria-label="Bookings by library" className="flex flex-col gap-3">
              {data.by_library.map((row) => (
                <li key={row.library_id} className="flex flex-col gap-1">
                  <div className="flex justify-between gap-3 text-sm text-slate-800">
                    <span>{row.name}</span>
                    <span className="tabular-nums">
                      {row.bookings} bookings · {row.unique_students} students
                    </span>
                  </div>
                  <ProgressBar value={row.bookings} max={topMax} label={`${row.name}: ${row.bookings} bookings`} />
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function SubscriptionSection({ range }: { range: DateRange }) {
  const valid = range.to >= range.from;
  const query = useQuery({
    queryKey: queryKeys.platformSubscriptions(range),
    queryFn: () => fetchPlatformSubscriptions(range),
    enabled: valid,
  });
  if (!valid) return null;
  if (query.isPending) return <LoadingList label="Loading subscription analytics" rows={2} />;
  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We could not load subscription analytics." />;
  }
  const data = query.data;
  const payments = data.student_payments_online;
  return (
    <div className="flex flex-col gap-4">
      <Grid>
        <StatCard label="Average bookings per library" value={average(data.averages_per_library.bookings)} hint={`Across all ${data.libraries} libraries, in range`} />
        <StatCard label="Average unique students per library" value={average(data.averages_per_library.unique_booking_students)} hint="Distinct booking students at each library" />
        <StatCard
          label="Online student payments"
          value={`${payments.successful} paid · ${payments.failed} failed`}
          hint={`${formatMoney(payments.amount_successful)} paid to libraries. Not LibraryHive revenue.`}
        />
      </Grid>
      <Alert tone="warning" title="Not available yet: subscription and revenue metrics">
        <ul className="flex list-disc flex-col gap-1 pl-5">
          {data.unavailable.map((item) => (
            <li key={item.key}>
              <strong>{item.label}.</strong> {item.reason}
            </li>
          ))}
        </ul>
      </Alert>
    </div>
  );
}

const DEFINITIONS: [string, string][] = [
  ["Booking", "One membership record. It exists only after a successful payment or an owner admission, so every booking is a confirmed seat."],
  ["Unique booking students", "Distinct students with a booking. A student with 10 bookings is counted once."],
  ["Monthly active students", "Distinct students with a booking in the current calendar month."],
  ["Repeat booking rate", "Of the students who booked in the range, the share who have more than one booking in total."],
  ["Abandoned holds", "A seat was held for payment but the hold expired or was cancelled. Paid bookings cannot be cancelled in the product."],
  ["Dates", "Business days in India (Asia/Kolkata), both ends of the range included."],
];

/** `/platform`: the LibraryHive team usage overview. Aggregates only; no personal data is shown. */
export function PlatformOverviewScreen() {
  const [state, setState] = useDateRange();
  const [granularity, setGranularity] = useState<Granularity>("day");
  const { range } = state;
  return (
    <Page className="max-w-7xl">
      <PageHeader
        title="Platform analytics"
        description="How students and libraries are using LibraryHive. Internal: visible to the LibraryHive team only."
        actions={<RangeFilter value={state} onChange={setState} />}
      />
      <Section id="overview" title="Platform overview" hint="All time, except monthly active students.">
        <OverviewSection />
      </Section>
      <Section id="bookings" title="Booking analytics" hint={`${range.from} to ${range.to}`}>
        <BookingsSection range={range} granularity={granularity} onGranularity={setGranularity} />
      </Section>
      <Section id="subscriptions" title="Subscriptions and revenue" hint="Only metrics the current data can answer accurately.">
        <SubscriptionSection range={range} />
      </Section>
      <details className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
        <summary className="cursor-pointer font-medium text-slate-900">How each number is calculated</summary>
        <dl className="mt-3 grid gap-3 sm:grid-cols-2">
          {DEFINITIONS.map(([term, text]) => (
            <div key={term}>
              <dt className="font-medium text-slate-900">{term}</dt>
              <dd className="text-slate-600">{text}</dd>
            </div>
          ))}
        </dl>
      </details>
    </Page>
  );
}
