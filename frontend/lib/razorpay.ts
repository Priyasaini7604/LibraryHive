/**
 * Razorpay Checkout loader (UI_ARCHITECTURE.md 5.3). `checkout.js` is fetched only when a payment starts, so it
 * is never loaded on other pages. The key id comes from the server's order response (#41); no key is
 * configured in the frontend. A checkout callback is only a hint: the server verifies the signature.
 */

import type { PaymentOrder } from "./types";

const SCRIPT_URL = "https://checkout.razorpay.com/v1/checkout.js";

export interface RazorpaySuccess {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

interface RazorpayOptions {
  key: string;
  order_id: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  prefill: { name: string; email: string; contact: string };
  theme: { color: string };
  handler: (response: RazorpaySuccess) => void;
  modal: { ondismiss: () => void };
}

interface RazorpayInstance {
  open: () => void;
  on: (event: "payment.failed", handler: (response: { error?: { description?: string } }) => void) => void;
}

type RazorpayConstructor = new (options: RazorpayOptions) => RazorpayInstance;

declare global {
  interface Window {
    Razorpay?: RazorpayConstructor;
  }
}

let loading: Promise<RazorpayConstructor> | null = null;

/** Load checkout.js once. Rejects if the script is blocked or the network is down. */
export function loadRazorpay(): Promise<RazorpayConstructor> {
  if (typeof window === "undefined") return Promise.reject(new Error("Checkout needs a browser."));
  if (window.Razorpay) return Promise.resolve(window.Razorpay);
  loading ??= new Promise<RazorpayConstructor>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_URL;
    script.async = true;
    script.onload = () => (window.Razorpay ? resolve(window.Razorpay) : reject(new Error("Checkout did not start.")));
    script.onerror = () => {
      loading = null;
      reject(new Error("Checkout could not be loaded."));
    };
    document.head.appendChild(script);
  });
  return loading;
}

export interface CheckoutHandlers {
  onSuccess: (result: RazorpaySuccess) => void;
  onDismiss: () => void;
  onFailure: (message: string) => void;
}

/** Open the checkout window for an order created by the server. */
export async function openCheckout(order: PaymentOrder, handlers: CheckoutHandlers): Promise<void> {
  const Razorpay = await loadRazorpay();
  const instance = new Razorpay({
    key: order.key_id,
    order_id: order.order_id,
    amount: order.amount_paise,
    currency: order.currency,
    name: "LibraryHive",
    description: order.description,
    prefill: { name: order.prefill.name, email: order.prefill.email, contact: order.prefill.phone },
    theme: { color: "#4F5EE8" },
    handler: handlers.onSuccess,
    modal: { ondismiss: handlers.onDismiss },
  });
  instance.on("payment.failed", (response) =>
    handlers.onFailure(response.error?.description || "The payment did not go through."),
  );
  instance.open();
}
