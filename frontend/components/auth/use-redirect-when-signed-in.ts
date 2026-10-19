"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth-context";

/**
 * Send a signed-in visitor on to `target` (null = stay). Used by the auth screens so that a
 * successful login, registration or claim, and a visit by someone already signed in, behave the same.
 */
export function useRedirectWhenSignedIn(target: string | null): boolean {
  const { status } = useAuth();
  const router = useRouter();
  const redirecting = status === "authenticated" && target !== null;

  useEffect(() => {
    if (redirecting) router.replace(target);
  }, [redirecting, target, router]);

  return redirecting;
}
