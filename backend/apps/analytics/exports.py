"""CSV exports for owners (#87, DASH-06).

A cell that starts with `=`, `+`, `-` or `@` (or a tab or carriage return) would be run as a formula by a
spreadsheet, so it is prefixed with an apostrophe. The file is streamed row by row.
"""

import csv
from collections.abc import Iterable, Iterator

from django.http import StreamingHttpResponse

DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(DANGEROUS_PREFIXES) else text


class _Echo:
    def write(self, value):
        return value


def stream_csv(filename: str, header: list[str], rows: Iterable[list]) -> StreamingHttpResponse:
    writer = csv.writer(_Echo())

    def generate() -> Iterator[str]:
        yield writer.writerow(header)
        for row in rows:
            yield writer.writerow([safe_cell(cell) for cell in row])

    response = StreamingHttpResponse(generate(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    return response


MEMBER_HEADER = ["Name", "Phone", "Email", "Seat", "Plan", "Source", "Status", "Start date", "Next due date"]


def member_rows(queryset) -> Iterator[list]:
    for m in queryset.iterator(chunk_size=500):
        yield [
            m.student.name,
            m.student.phone,
            m.student.email,
            m.seat.label,
            m.plan.name,
            m.source,
            m.status,
            m.start_date,
            m.next_due_date,
        ]


PAYMENT_HEADER = [
    "Receipt",
    "Date",
    "Student",
    "Phone",
    "Amount",
    "Method",
    "Channel",
    "Status",
    "Purpose",
    "Period start",
    "Period end",
]


def payment_rows(queryset) -> Iterator[list]:
    for p in queryset.iterator(chunk_size=500):
        yield [
            p.receipt_number,
            p.event_at.date().isoformat() if p.event_at else "",
            p.student.name,
            p.student.phone,
            p.amount,
            p.method,
            p.channel,
            p.status,
            p.purpose,
            p.period_start,
            p.period_end,
        ]


ATTENDANCE_HEADER = ["Date", "Student", "Seat", "Check in", "Check out", "Minutes", "Status"]


def attendance_rows(queryset) -> Iterator[list]:
    for r in queryset.iterator(chunk_size=500):
        yield [
            r.date,
            r.student.name,
            r.seat.label if r.seat else "",
            r.check_in_at.isoformat(),
            r.check_out_at.isoformat() if r.check_out_at else "",
            r.duration_minutes,
            r.status,
        ]
