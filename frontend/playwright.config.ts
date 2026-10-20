import { defineConfig, devices } from "@playwright/test";

/**
 * Browser end-to-end suite. It runs against its OWN stack and database, never a development server:
 *   backend   http://127.0.0.1:8010   (config.settings.e2e, fake payment gateway, database libraryhive_e2e)
 *   frontend  http://127.0.0.1:3010   (production build in .next-e2e)
 *
 * Required: E2E_DATABASE_URL pointing at the local database named exactly `libraryhive_e2e`. The backend
 * settings module refuses anything else; this file checks it first so a wrong value fails in seconds.
 * See e2e/README.md for the one-time database creation and the run commands.
 */

const BACKEND = "http://127.0.0.1:8010";
const FRONTEND = "http://127.0.0.1:3010";

function assertDedicatedDatabase(): void {
  const raw = process.env.E2E_DATABASE_URL ?? "";
  let name = "";
  let host = "";
  try {
    const url = new URL(raw);
    name = decodeURIComponent(url.pathname.replace(/^\//, ""));
    host = url.hostname;
  } catch {
    // handled below
  }
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(host);
  if (name !== "libraryhive_e2e" || !local) {
    throw new Error(
      "E2E_DATABASE_URL must point at the local database named exactly 'libraryhive_e2e' (see e2e/README.md). " +
        "Refusing to start: the browser suite never uses another database.",
    );
  }
  if (process.env.DATABASE_URL && process.env.DATABASE_URL === raw) {
    throw new Error("E2E_DATABASE_URL must not equal DATABASE_URL.");
  }
}

assertDedicatedDatabase();

const python = process.env.E2E_PYTHON ?? "python";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  // One shared database: run files one after another.
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: FRONTEND,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `"${python}" manage.py runserver 127.0.0.1:8010 --noreload`,
      cwd: "../backend",
      url: `${BACKEND}/api/v1/health/`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { DJANGO_SETTINGS_MODULE: "config.settings.e2e", E2E_FRONTEND_URL: FRONTEND },
    },
    {
      command: "npm run build && npx next start -H 127.0.0.1 -p 3010",
      url: `${FRONTEND}/login`,
      reuseExistingServer: false,
      timeout: 600_000,
      env: {
        NEXT_DIST_DIR: ".next-e2e",
        NEXT_PUBLIC_API_URL: `${BACKEND}/api/v1`,
        BACKEND_ORIGIN: BACKEND,
        NODE_ENV: "production",
      },
    },
  ],
});
