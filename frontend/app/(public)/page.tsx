import { ArrowRight, Armchair, Search, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

const POINTS = [
  { Icon: Search, title: "Find a library", text: "Search by area or name and compare plans, amenities and photos." },
  { Icon: Armchair, title: "See your seat", text: "Pick a seat on the library's live map before you pay." },
  { Icon: ShieldCheck, title: "Pay securely", text: "Payments are verified by our server, never by your browser." },
];

/** Landing page (UI_ARCHITECTURE.md decision U3): an editorial hero, three numbered steps and a closing call to action. */
export default function LandingPage() {
  return (
    <div className="flex flex-col">
      <section className="relative isolate overflow-hidden">
        <div aria-hidden="true" className="pointer-events-none absolute -left-32 -top-40 -z-10 size-[32rem] rounded-full bg-indigo-500/20 blur-3xl" />
        <div aria-hidden="true" className="pointer-events-none absolute -right-24 top-24 -z-10 size-[26rem] rounded-full bg-violet-500/15 blur-3xl" />
        <div className="mx-auto flex max-w-7xl flex-col items-start gap-8 px-4 pb-24 pt-20 sm:px-6 sm:pb-32 sm:pt-32">
          <p className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
            <span aria-hidden="true" className="size-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_2px_rgb(52_211_153/0.6)]" />
            Study libraries, live
          </p>
          <h1 className="max-w-4xl text-5xl font-extrabold leading-[1.02] tracking-[-0.035em] text-slate-900 sm:text-7xl">
            Your study seat,
            <span className="gradient-text block">sorted.</span>
          </h1>
          <p className="max-w-xl text-lg leading-relaxed text-slate-600 sm:text-xl">
            Find a study library near you, check which seats are free and book yours in minutes.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/discover">
                Find a library <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="secondary">
              <Link href="/register">Run a library? Sign up</Link>
            </Button>
          </div>
        </div>
      </section>

      <section aria-labelledby="how-heading" className="border-t border-white/5">
        <div className="mx-auto flex max-w-7xl flex-col gap-10 px-4 py-20 sm:px-6">
          <h2 id="how-heading" className="max-w-2xl text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
            Three steps from search to a seat of your own.
          </h2>
          <ul className="grid gap-5 md:grid-cols-3">
            {POINTS.map(({ Icon, title, text }, index) => (
              <li
                key={title}
                className="card-glow relative flex flex-col gap-4 overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 sm:p-7"
              >
                <span aria-hidden="true" className="font-display text-sm font-bold tracking-widest text-blue-400">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span aria-hidden="true" className="flex size-11 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
                  <Icon className="size-5" />
                </span>
                <h3 className="text-xl font-semibold text-slate-900">{title}</h3>
                <p className="text-slate-600">{text}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section aria-labelledby="cta-heading" className="px-4 pb-24 sm:px-6">
        <div className="relative mx-auto flex max-w-7xl flex-col items-start gap-6 overflow-hidden rounded-3xl border border-white/10 bg-white p-8 sm:p-14">
          <div aria-hidden="true" className="pointer-events-none absolute -right-20 -top-24 size-80 rounded-full bg-indigo-500/25 blur-3xl" />
          <h2 id="cta-heading" className="relative max-w-2xl text-3xl font-extrabold tracking-tight text-slate-900 sm:text-5xl">
            Ready to find your corner?
          </h2>
          <p className="relative max-w-lg text-lg text-slate-600">Browse libraries near you, or list your own and let students book seats online.</p>
          <div className="relative flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/discover">Browse libraries</Link>
            </Button>
            <Button asChild size="lg" variant="ghost">
              <Link href="/register">List your library</Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
