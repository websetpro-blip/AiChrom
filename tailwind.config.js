/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { 
    extend: { 
      colors: { 
        brand: { 
          500: "#F59E0B", 
          600: "#F97316" 
        } 
      } 
    } 
  },
  plugins: []
};
