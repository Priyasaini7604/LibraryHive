import type { Metadata } from "next";

import { OnboardingWizard } from "@/components/owner/onboarding-wizard";

export const metadata: Metadata = { title: "Set up your library" };

export default function OwnerOnboardingPage() {
  return <OnboardingWizard />;
}
