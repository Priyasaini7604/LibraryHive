"use client";

import { Toaster as Sonner } from "sonner";

/** Toasts for low-stakes confirmations (UI_ARCHITECTURE.md 10.4). Use `toast()` from "sonner". */
export function Toaster() {
  return <Sonner position="bottom-center" richColors closeButton duration={4000} />;
}
