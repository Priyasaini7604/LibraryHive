import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthCardSkeleton } from "@/components/auth/auth-card";
import { ClaimFlow } from "@/components/auth/claim-flow";

export const metadata: Metadata = { title: "Link your membership" };

export default function ClaimPage() {
  return (
    <Suspense fallback={<AuthCardSkeleton />}>
      <ClaimFlow />
    </Suspense>
  );
}
