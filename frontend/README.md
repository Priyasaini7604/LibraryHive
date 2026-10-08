# LibraryHive frontend

Next.js 16 (App Router) · React 19 · TypeScript (strict) · Tailwind CSS 4 · TanStack Query · react-hook-form + zod · Radix primitives.
Design: `UI_ARCHITECTURE.md` at the repository root.

## Setup

Requires Node.js 20.9+ and the backend running (see the root `README.md`).

```bash
cd frontend
npm ci
cp .env.example .env.local     # NEXT_PUBLIC_API_URL, BACKEND_ORIGIN, MEDIA_ORIGIN
npm run dev                    # http://localhost:3000
```

## Quality checks (the same ones CI runs)

```bash
npm run lint        # ESLint: Next.js, TypeScript, jsx-a11y, no `any`, no direct fetch()
npm run typecheck   # next typegen + tsc --noEmit (strict)
npm test            # Vitest + Testing Library + axe-core
npm run build
```

## How the pieces fit

| Concern | Where |
|---|---|
| All API calls (envelope, errors, token refresh, server clock) | `lib/api-client.ts` (the only place allowed to call `fetch`) |
| Access token, in memory only (SEC-1) | `lib/auth.ts` |
| Session state and login/logout | `lib/auth-context.tsx` (`useAuth`) |
| Auth endpoints proxied same-origin so the HttpOnly refresh cookie is first-party | `next.config.ts` rewrite of `/api/v1/auth/*` |
| Content-Security-Policy with per-request nonce | `proxy.ts` + `lib/security/csp.ts` |
| Error codes → friendly messages | `lib/errors.ts` |
| Money, dates (always Asia/Kolkata), phones | `lib/format.ts` |
| Navigation, role homes, safe `?next=` redirects | `lib/navigation.ts` |
| Role guard for `/student` and `/owner` | `components/layout/auth-guard.tsx` |
| Shells (public, student, owner) | `components/layout/shells.tsx` |
| UI kit | `components/ui/*` |

The backend enforces every permission; the route guard only improves the experience.

## Generated API types

With the backend running locally: `npm run api:types` writes `lib/api-types.gen.ts` from `/api/v1/schema/`.
