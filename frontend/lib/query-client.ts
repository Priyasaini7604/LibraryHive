import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "./errors";

/** Shared query defaults (UI_ARCHITECTURE.md 9.3): never retry client errors. */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: true,
        retry: (failureCount, error) => {
          if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
          return failureCount < 2;
        },
      },
      mutations: { retry: false },
    },
  });
}

export const queryKeys = {
  me: ["auth", "me"] as const,
};
