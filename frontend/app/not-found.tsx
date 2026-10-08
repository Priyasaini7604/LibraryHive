import Link from "next/link";

import { buttonClasses } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main id="main" className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
      <p className="text-sm font-semibold text-blue-700">404</p>
      <h1 className="text-2xl font-semibold text-slate-900">Page not found</h1>
      <p className="text-slate-600">The page you&apos;re looking for doesn&apos;t exist or has moved.</p>
      <Link href="/discover" className={buttonClasses("primary")}>
        Find a library
      </Link>
    </main>
  );
}
