"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { DomainBars, OccupancyBar } from "@/components/charts/bars";
import { StatCard } from "@/components/charts/stat-card";
import { ExportButton } from "@/components/owner/export-button";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { DateField } from "@/components/ui/input";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { CATEGORY_LABEL, METHOD_LABEL } from "@/components/ui/status-badges";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/surface";
import { fetchComplaintReport, fetchDomainReport, fetchOccupancyReport, fetchRevenueReport } from "@/lib/api/operations";
import { businessDate, formatMoney } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { ComplaintCategory, PaymentMethod } from "@/lib/types";

const STATUS_LABEL: Record<string, string> = { open: "Open", in_progress: "In progress", resolved: "Resolved" };
const PURPOSE_LABEL: Record<string, string> = { new_membership: "New memberships", renewal: "Renewals" };

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <h2 id={id} className="text-lg font-semibold text-slate-900">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Breakdown({ rows, empty }: { rows: [string, string][]; empty: string }) {
  if (rows.length === 0) return <p className="text-sm text-slate-600">{empty}</p>;
  return (
    <ul className="flex flex-col gap-1 text-sm">
      {rows.map(([label, value]) => (
        <li key={label} className="flex justify-between gap-3">
          <span>{label}</span>
          <span className="tabular-nums">{value}</span>
        </li>
      ))}
    </ul>
  );
}

function OccupancySection() {
  const query = useQuery({ queryKey: queryKeys.ownerOccupancy, queryFn: fetchOccupancyReport });
  if (query.isPending) return <LoadingList label="Loading occupancy" rows={1} />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load occupancy." />;
  const { counts, by_row: rows } = query.data;
  if (counts.total === 0) return <EmptyState title="No seats yet" description="Add seats to see occupancy." />;
  return (
    <div className="flex flex-col gap-4">
      <OccupancyBar label="Seat occupancy" occupied={counts.occupied} reserved={counts.reserved} empty={counts.empty} disabled={counts.total - counts.occupied - counts.reserved - counts.empty} />
      <table className="w-full max-w-xl text-left text-sm">
        <caption className="sr-only">Seats by row</caption>
        <thead className="text-xs uppercase text-slate-600">
          <tr>
            <th scope="col" className="py-1 pr-3">Row</th>
            <th scope="col" className="py-1 pr-3">Taken</th>
            <th scope="col" className="py-1 pr-3">Reserved</th>
            <th scope="col" className="py-1 pr-3">Free</th>
            <th scope="col" className="py-1">Total</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.row_label || "none"} className="border-t border-slate-200">
              <th scope="row" className="py-1 pr-3 font-medium">{row.row_label || "—"}</th>
              <td className="py-1 pr-3 tabular-nums">{row.occupied}</td>
              <td className="py-1 pr-3 tabular-nums">{row.reserved}</td>
              <td className="py-1 pr-3 tabular-nums">{row.empty}</td>
              <td className="py-1 tabular-nums">{row.total}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RevenueSection() {
  const today = businessDate();
  const [from, setFrom] = useState(`${today.slice(0, 8)}01`);
  const [to, setTo] = useState(today);
  const range = { from, to };
  const valid = Boolean(from) && Boolean(to) && from <= to && (Date.parse(to) - Date.parse(from)) / 86_400_000 <= 365;
  const query = useQuery({ queryKey: queryKeys.ownerRevenue(range), queryFn: () => fetchRevenueReport(range), enabled: valid });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <FormField label="From" className="sm:w-44">
          <DateField value={from} max={to} onChange={(event) => setFrom(event.target.value)} />
        </FormField>
        <FormField label="To" className="sm:w-44">
          <DateField value={to} min={from} max={today} onChange={(event) => setTo(event.target.value)} />
        </FormField>
        <ExportButton kind="payments" query={range} label="Export payments" />
      </div>
      {!valid ? (
        <p role="alert" className="text-sm text-red-700">Choose a range of at most 366 days, with the start before the end.</p>
      ) : query.isPending ? (
        <LoadingList label="Loading revenue" rows={1} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load revenue." />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <StatCard label="Revenue" value={formatMoney(query.data.total)} hint="Paid payments only" />
            <StatCard label="Payments" value={query.data.count} />
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader><CardTitle>By method</CardTitle></CardHeader>
              <CardContent>
                <Breakdown empty="No payments in this range." rows={Object.entries(query.data.by_method).map(([k, v]) => [METHOD_LABEL[k as PaymentMethod] ?? k, `${formatMoney(v.total)} · ${v.count}`])} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>By purpose</CardTitle></CardHeader>
              <CardContent>
                <Breakdown empty="No payments in this range." rows={Object.entries(query.data.by_purpose).map(([k, v]) => [PURPOSE_LABEL[k] ?? k, `${formatMoney(v.total)} · ${v.count}`])} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>By month</CardTitle></CardHeader>
              <CardContent>
                <Breakdown empty="No payments in this range." rows={query.data.by_month.map((m) => [m.month, `${formatMoney(m.total)} · ${m.count}`])} />
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function ComplaintSection() {
  const query = useQuery({ queryKey: queryKeys.ownerComplaintReport, queryFn: () => fetchComplaintReport() });
  if (query.isPending) return <LoadingList label="Loading complaints report" rows={1} />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load the complaints report." />;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Card>
        <CardHeader><CardTitle>By status</CardTitle></CardHeader>
        <CardContent>
          <Breakdown empty="No complaints yet." rows={Object.entries(query.data.by_status).map(([k, v]) => [STATUS_LABEL[k] ?? k, String(v)])} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>By topic</CardTitle></CardHeader>
        <CardContent>
          <Breakdown empty="No complaints yet." rows={Object.entries(query.data.by_category).map(([k, v]) => [CATEGORY_LABEL[k as ComplaintCategory] ?? k, String(v)])} />
        </CardContent>
      </Card>
    </div>
  );
}

function DomainSection() {
  const query = useQuery({ queryKey: ["owner", "reports", "domains"], queryFn: fetchDomainReport });
  if (query.isPending) return <LoadingList label="Loading exams" rows={1} />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load the exam breakdown." />;
  return query.data.length === 0 ? <p className="text-sm text-slate-600">Members haven&apos;t chosen an exam yet.</p> : <DomainBars rows={query.data} />;
}

/** `/owner/reports`: occupancy, revenue, complaints and exam mix, with CSV exports (#83-#87). */
export function ReportsScreen() {
  return (
    <Page>
      <PageHeader
        title="Reports"
        description="Figures for your library. Revenue counts paid payments only."
        actions={
          <>
            <ExportButton kind="members" label="Export members" />
            <Button asChild variant="secondary">
              <Link href="/owner/activity">Activity log</Link>
            </Button>
          </>
        }
      />
      <Section id="occupancy" title="Seat occupancy">
        <OccupancySection />
      </Section>
      <Section id="revenue" title="Revenue">
        <RevenueSection />
      </Section>
      <Section id="complaints" title="Complaints">
        <ComplaintSection />
      </Section>
      <Section id="domains" title="Members by exam">
        <DomainSection />
      </Section>
    </Page>
  );
}
