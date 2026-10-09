import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import jsxA11y from "eslint-plugin-jsx-a11y";

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    // Accessibility rules (UI_ARCHITECTURE.md section 11); the plugin is registered by eslint-config-next.
    rules: {
      ...jsxA11y.flatConfigs.recommended.rules,
      // No `any` in API payloads, props or state (AGENTS.md 2.3).
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      // Components must call the API through lib/api-client.ts, never fetch directly.
      "no-restricted-syntax": [
        "error",
        {
          selector: "CallExpression[callee.name='fetch']",
          message: "Use lib/api-client.ts instead of calling fetch() directly.",
        },
      ],
    },
  },
  {
    // The API client and its tests are the only places allowed to call fetch().
    files: ["lib/api-client.ts", "tests/**"],
    rules: { "no-restricted-syntax": "off" },
  },
  globalIgnores([".next/**", "out/**", "build/**", "coverage/**", "next-env.d.ts", "lib/api-types.gen.ts"]),
]);
