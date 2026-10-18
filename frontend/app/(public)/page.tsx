import { Armchair, Search, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

const POINTS = [
  { Icon: Search, title: "Find a library", text: "Search by area or name and compare plans, amenities and photos." },
  { Icon: Armchair, title: "See your seat", text: "Pick a seat on the library's live map before you pay." },
  { Icon: ShieldCheck, title: "Pay securely", text: "Payments are verified by our server, never by your browser." },
];

/** Minimal landing page (UI_ARCHITECTURE.md decision U3). */
export default function LandingPage() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-10 px-4 py-12 sm:px-6">
      <section className="flex flex-col items-start gap-4">
        <h1 className="text-3xl font-semibold text-slate-900 sm:text-4xl">Your study seat, sorted.</h1>
        <p className="max-w-2xl text-lg text-slate-700">
          Find a study library near you, check which seats are free and book yours in minutes.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button asChild size="lg">
            <Link href="/discover">Find a library</Link>
          </Button>
          <Button asChild size="lg" variant="secondary">
            <Link href="/register">Run a library? Sign up</Link>
          </Button>
        </div>
      </section>
      <section aria-label="How it works">
        <ul className="grid gap-4 sm:grid-cols-3">
          {POINTS.map(({ Icon, title, text }) => (
            <li key={title} className="flex flex-col gap-2 rounded-xl border border-slate-200 p-5">
              <Icon aria-hidden="true" className="size-6 text-blue-600" />
              <h2 className="font-semibold text-slate-900">{title}</h2>
              <p className="text-sm text-slate-700">{text}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
