"use client";

import { useQuery } from "@tanstack/react-query";
import { PartyPopper } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AddSeatsDialog } from "@/components/owner/add-seats-dialog";
import { LibraryProfileForm } from "@/components/owner/library-profile-form";
import { PhotosPanel } from "@/components/owner/photos-panel";
import { PlansPanel } from "@/components/owner/plans-panel";
import { Button } from "@/components/ui/button";
import { Stepper, type Step } from "@/components/ui/navigation";
import { Page, PageHeader } from "@/components/ui/page";
import { ErrorState, FullPageSkeleton } from "@/components/ui/states";
import { Alert } from "@/components/ui/surface";
import { fetchOwnerLibrary } from "@/lib/api/libraries";
import { queryKeys } from "@/lib/query-keys";

type StepId = "profile" | "plans" | "photos" | "seats" | "live";
const ORDER: StepId[] = ["profile", "plans", "photos", "seats", "live"];

/**
 * `/owner/onboarding` (UI_ARCHITECTURE.md 5.6): profile, plans, photos, seats, then live. It opens at the first
 * step that still needs work. Publishing is automatic (decision D12): the server publishes as soon as the
 * profile, location, a plan and a seat exist, so there is no "publish" button.
 */
export function OnboardingWizard() {
  const query = useQuery({ queryKey: queryKeys.ownerLibrary, queryFn: fetchOwnerLibrary });
  const [chosen, setChosen] = useState<StepId | null>(null);
  const [addingSeats, setAddingSeats] = useState(false);

  if (query.isPending) return <FullPageSkeleton />;
  if (query.isError) {
    return (
      <Page>
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your library." />
      </Page>
    );
  }

  const library = query.data;
  const checklist = library?.publish_checklist;
  const done: Record<StepId, boolean> = {
    profile: library !== null,
    plans: Boolean(checklist?.has_active_plan),
    photos: false, // optional: counted done once the owner has moved past it
    seats: Boolean(checklist?.has_active_seat),
    live: Boolean(library?.is_published),
  };
  const firstIncomplete = (["profile", "plans", "seats"] as StepId[]).find((id) => !done[id]) ?? "live";
  const current = chosen ?? firstIncomplete;
  const index = ORDER.indexOf(current);
  const steps: Step[] = [
    { id: "profile", label: "Your library", complete: done.profile },
    { id: "plans", label: "Plans and prices", complete: done.plans },
    { id: "photos", label: "Photos (optional)", complete: index > ORDER.indexOf("photos") },
    { id: "seats", label: "Seats", complete: done.seats },
    { id: "live", label: "Go live", complete: done.live },
  ];
  const canContinue = current === "photos" || (current !== "live" && done[current]);

  return (
    <Page className="max-w-5xl">
      <PageHeader title="Set up your library" description="A few steps and students can find you. You can change everything later." />
      <div className="grid gap-6 lg:grid-cols-[14rem_1fr]">
        <Stepper steps={steps} currentId={current} />
        <div className="flex min-w-0 flex-col gap-6">
          {current === "profile" && <LibraryProfileForm library={library} />}
          {current === "plans" && <PlansPanel />}
          {current === "photos" && <PhotosPanel />}
          {current === "seats" && (
            <section aria-labelledby="seats-step" className="flex flex-col gap-3">
              <h2 id="seats-step" className="text-lg font-semibold text-slate-900">
                Seats
              </h2>
              <p className="text-slate-700">Add your seats. A grid such as rows A to C with 10 seats each is the quickest way; you can rename and manage them later.</p>
              {done.seats ? <Alert tone="success">You have seats. You can add more or manage them from the Seats page.</Alert> : null}
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => setAddingSeats(true)}>Add seats</Button>
                <Button asChild variant="secondary">
                  <Link href="/owner/seats">Open the seat manager</Link>
                </Button>
              </div>
              {addingSeats && <AddSeatsDialog open onOpenChange={setAddingSeats} />}
            </section>
          )}
          {current === "live" && (
            <section aria-labelledby="live-step" className="flex flex-col items-start gap-3">
              <h2 id="live-step" className="flex items-center gap-2 text-lg font-semibold text-slate-900">
                <PartyPopper aria-hidden="true" className="size-5" /> {done.live ? "Your library is live" : "Almost there"}
              </h2>
              {done.live && library ? (
                <>
                  <p className="text-slate-700">Students can now find your library, see its plans and book seats.</p>
                  <div className="flex flex-wrap gap-2">
                    <Button asChild>
                      <Link href="/owner">Go to your dashboard</Link>
                    </Button>
                    <Button asChild variant="secondary">
                      <Link href={`/libraries/${library.id}`}>View your public page</Link>
                    </Button>
                  </div>
                </>
              ) : (
                <Alert tone="info">Your library goes live as soon as it has a profile with a location, an active plan and at least one seat. Go back to finish the missing steps.</Alert>
              )}
            </section>
          )}

          {current !== "live" || !done.live ? (
            <div className="flex justify-between gap-2 border-t border-slate-200 pt-4">
              <Button variant="secondary" disabled={index === 0} onClick={() => setChosen(ORDER[index - 1] ?? "profile")}>
                Back
              </Button>
              {current !== "live" && (
                <Button disabled={!canContinue} onClick={() => setChosen(ORDER[index + 1] ?? "live")}>
                  {current === "photos" ? "Continue" : "Next"}
                </Button>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </Page>
  );
}
