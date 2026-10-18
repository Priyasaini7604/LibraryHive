/** TanStack Query keys, one place so invalidation never misses a spelling (UI_ARCHITECTURE.md 9.3). */

export const queryKeys = {
  domains: ["meta", "domains"] as const,
  amenities: ["meta", "amenities"] as const,
  libraries: (filters: object) => ["libraries", "list", filters] as const,
  library: (id: string) => ["libraries", "detail", id] as const,
  ownerLibrary: ["owner", "library"] as const,
  ownerPlans: ["owner", "library", "plans"] as const,
  ownerPhotos: ["owner", "library", "photos"] as const,
};
