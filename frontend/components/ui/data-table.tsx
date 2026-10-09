import { cn } from "@/lib/cn";

export interface Column<Row> {
  key: string;
  header: string;
  cell: (row: Row) => React.ReactNode;
  /** The column used as the card title on phones. */
  primary?: boolean;
  /** Hide this column in the phone card layout. */
  hideOnMobile?: boolean;
  className?: string;
}

export interface DataTableProps<Row> {
  caption: string;
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  rowActions?: (row: Row) => React.ReactNode;
}

/**
 * A real <table> from 768px up and a stacked card list below, from the same
 * column definitions (UI_ARCHITECTURE.md 8). Only one layout is visible (and
 * exposed to assistive technology) at a time.
 */
export function DataTable<Row>({ caption, columns, rows, rowKey, rowActions }: DataTableProps<Row>) {
  const primary = columns.find((column) => column.primary) ?? columns[0];
  const secondary = columns.filter((column) => column !== primary && !column.hideOnMobile).slice(0, 3);

  return (
    <>
      <div className="hidden overflow-x-auto rounded-xl border border-slate-200 bg-white md:block">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
            <tr>
              {columns.map((column) => (
                <th key={column.key} scope="col" className={cn("px-4 py-3 font-medium", column.className)}>
                  {column.header}
                </th>
              ))}
              {rowActions && (
                <th scope="col" className="px-4 py-3">
                  <span className="sr-only">Actions</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {rows.map((row) => (
              <tr key={rowKey(row)} className="hover:bg-slate-50">
                {columns.map((column) => (
                  <td key={column.key} className={cn("px-4 py-3 text-slate-900", column.className)}>
                    {column.cell(row)}
                  </td>
                ))}
                {rowActions && <td className="px-4 py-3 text-right">{rowActions(row)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul aria-label={caption} className="flex flex-col gap-3 md:hidden">
        {rows.map((row) => (
          <li key={rowKey(row)} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="font-medium text-slate-900">{primary?.cell(row)}</div>
              {rowActions?.(row)}
            </div>
            <dl className="mt-2 grid gap-1 text-sm">
              {secondary.map((column) => (
                <div key={column.key} className="flex justify-between gap-3">
                  <dt className="text-slate-600">{column.header}</dt>
                  <dd className="text-right text-slate-900">{column.cell(row)}</dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ul>
    </>
  );
}

/** Filter controls row; filters live in the URL query string (UI_ARCHITECTURE.md 9.3). */
export function FilterBar({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div role="search" aria-label={label} className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
      {children}
    </div>
  );
}
