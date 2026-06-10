/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}", "./lib/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        bg: "#080d12",
        panel: "#101820",
        ink: "#eef5f3",
        muted: "#91a4ad",
        accent: "#21c77a",
        line: "rgba(145, 164, 173, 0.18)",
      },
    },
  },
  plugins: [],
};
