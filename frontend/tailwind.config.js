/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          primary: "#FAFAF7",
          card: "#FFFFFF",
          muted: "#F2F1EC",
          tinted: "#F4F1EA",
          inverse: "#0F1620",
        },
        ink: {
          primary: "#1A1A1A",
          secondary: "#4A4A4A",
          muted: "#8A8A8A",
          inverse: "#FAFAF7",
        },
        border: {
          subtle: "#E6E3DB",
          strong: "#D4D0C4",
        },
        accent: {
          primary: "#1F4E79",
          soft: "#EAF1F8",
          teal: "#2A7F8C",
        },
        signal: {
          positive: "#3F7D58",
          "positive-soft": "#E8F5E9",
          warn: "#B8732A",
          "warn-soft": "#FFF3E0",
          alert: "#B43A3A",
          "alert-soft": "#FFEBEE",
        },
      },
      fontFamily: {
        heading: ["Newsreader", "Georgia", "serif"],
        body: ["Geist", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        mono: ["Geist Mono", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        // Newsreader display sizes from pencil-new.pen
        "display-hero": ["62px", { lineHeight: "1.05", letterSpacing: "-0.025em" }],
        "display-result": ["42px", { lineHeight: "1.12", letterSpacing: "-0.024em" }],
        "display-section": ["34px", { lineHeight: "1.15", letterSpacing: "-0.018em" }],
        "display-meta": ["30px", { lineHeight: "1.1", letterSpacing: "-0.01em" }],
        "display-mhero": ["28px", { lineHeight: "1.15", letterSpacing: "-0.021em" }],
        "display-mresult": ["26px", { lineHeight: "1.2", letterSpacing: "-0.023em" }],
        "display-mfeat": ["22px", { lineHeight: "1.2", letterSpacing: "-0.018em" }],
        "display-card": ["20px", { lineHeight: "1.25", letterSpacing: "-0.015em" }],
        "display-check": ["19px", { lineHeight: "1.3", letterSpacing: "-0.011em" }],
        "display-step": ["42px", { lineHeight: "1", letterSpacing: "-0.024em" }],
        "display-gauge": ["56px", { lineHeight: "1", letterSpacing: "-0.036em" }],
        "display-gauge-m": ["48px", { lineHeight: "1", letterSpacing: "-0.021em" }],
      },
      spacing: {
        xs: "4px",
        sm: "8px",
        md: "16px",
        lg: "24px",
        xl: "32px",
        "2xl": "48px",
        "3xl": "64px",
        "4xl": "80px",
      },
      borderRadius: {
        card: "8px",
        "card-mobile": "10px",
        pill: "9999px",
        button: "6px",
        input: "6px",
        bar: "3px",
      },
      letterSpacing: {
        eyebrow: "0.16em",
        "eyebrow-tight": "0.12em",
        "eyebrow-wide": "0.2em",
        "mono-tag": "0.1em",
        "mono-meta": "0.06em",
      },
      boxShadow: {
        sm: "0 1px 3px rgba(15, 22, 32, 0.03)",
        md: "0 4px 12px rgba(15, 22, 32, 0.06)",
        // 2-layer card shadow from pencil-new.pen uploadCard
        card: "0 1px 3px rgba(15, 22, 32, 0.03), 0 12px 32px rgba(15, 22, 32, 0.05)",
      },
    },
  },
  plugins: [],
};
