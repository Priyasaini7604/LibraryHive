"use client";

import "./globals.css";

/** Last-resort error boundary for errors in the root layout itself. */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body>
        <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
          <h1 className="text-2xl font-semibold text-slate-900">Something went wrong</h1>
          <p className="text-slate-600">Please try again. If it keeps happening, contact support.</p>
          {error.digest && <p className="text-xs text-slate-500">Reference: {error.digest}</p>}
          <button
            type="button"
            onClick={reset}
            className="h-11 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700"
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
