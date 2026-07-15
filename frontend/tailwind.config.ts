import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        midnight: {
          base: "#0b1326",
          lowest: "#060e20",
          low: "#131b2e",
          panel: "#171f33",
          high: "#222a3d",
          highest: "#2d3449",
        },
        rag: {
          text: "#dae2fd",
          muted: "#c7c4d8",
          outline: "#464555",
          primary: "#c3c0ff",
          primaryStrong: "#4f46e5",
          secondary: "#89ceff",
          secondaryStrong: "#00a2e6",
          tertiary: "#4edea3",
          success: "#67f4b7",
          warning: "#ffd166",
          error: "#ffb4ab",
        },
      },
      fontFamily: {
        sans: ["Geist", "Inter", "Segoe UI", "Arial", "sans-serif"],
        mono: ["JetBrains Mono", "SFMono-Regular", "Consolas", "monospace"],
      },
      borderRadius: {
        rag: "4px",
        "rag-lg": "8px",
      },
      spacing: {
        sidebar: "280px",
        inspector: "360px",
      },
      boxShadow: {
        glass: "0 18px 50px rgba(0, 0, 0, 0.28)",
        active: "0 0 18px rgba(137, 206, 255, 0.16)",
      },
    },
  },
  plugins: [],
};

export default config;
