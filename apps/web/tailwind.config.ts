import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui"],
        display: ["var(--font-display)", "ui-serif", "serif"]
      },
      colors: {
        ink: "#0b0b0b",
        sub: "#52514e",
        muted: "#898781",
        paper: "#fafaf9",
        card: "#ffffff",
        line: "rgba(11,11,11,0.08)",
        accent: {
          DEFAULT: "#0d9488",
          deep: "#0f766e",
          soft: "#e9f5f3"
        },
        violet: {
          DEFAULT: "#4a3aa7",
          soft: "#efedfa"
        }
      },
      boxShadow: {
        card: "0 1px 2px rgba(11,11,11,0.04), 0 8px 24px rgba(11,11,11,0.05)"
      }
    }
  },
  plugins: []
};

export default config;
