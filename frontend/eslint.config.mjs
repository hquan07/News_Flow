import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // The dashboard consumes heterogeneous analytics payloads. These will be
      // tightened incrementally as API response contracts are generated.
      "@typescript-eslint/no-explicit-any": "off",
      // Initial state is intentionally hydrated from localStorage/API effects.
      "react-hooks/set-state-in-effect": "off",
    },
  },
]);

export default eslintConfig;
