"use client";

import { useQuery } from "@tanstack/react-query";

import { LibraryProfileForm } from "@/components/owner/library-profile-form";
import { PhotosPanel } from "@/components/owner/photos-panel";
import { PlansPanel } from "@/components/owner/plans-panel";
import { PublishChecklist } from "@/components/owner/publish-checklist";
import { Tabs, TabsContent, TabsList } from "@/components/ui/navigation";
import { ErrorState, FullPageSkeleton } from "@/components/ui/states";
import { fetchOwnerLibrary } from "@/lib/api/libraries";
import { queryKeys } from "@/lib/query-keys";

/** /owner/library: Profile, Plans and Photos tabs plus the go-live checklist (UI_ARCHITECTURE.md 5.6, 5.10). */
export function LibrarySettings() {
  const library = useQuery({ queryKey: queryKeys.ownerLibrary, queryFn: fetchOwnerLibrary });

  if (library.isPending) return <FullPageSkeleton />;
  if (library.isError) {
    return (
      <div className="p-4 sm:p-8">
        <ErrorState error={library.error} onRetry={() => void library.refetch()} title="We couldn't load your library." />
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-4 sm:p-8">
      <h1 className="text-2xl font-semibold text-slate-900">Your library</h1>
      {library.data === null ? (
        <LibraryProfileForm library={null} />
      ) : (
        <>
          <PublishChecklist library={library.data} />
          <Tabs defaultValue="profile" className="flex flex-col gap-5">
            <TabsList
              label="Library settings"
              items={[
                { value: "profile", label: "Profile" },
                { value: "plans", label: "Plans" },
                { value: "photos", label: "Photos" },
              ]}
            />
            <TabsContent value="profile">
              <LibraryProfileForm library={library.data} />
            </TabsContent>
            <TabsContent value="plans">
              <PlansPanel />
            </TabsContent>
            <TabsContent value="photos">
              <PhotosPanel />
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
