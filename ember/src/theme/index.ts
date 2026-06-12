export const colors = {
  bg: "#0E0B0A",
  card: "#1B1614",
  ember: "#FF5A2D",
  emberSoft: "#FF8A5C",
  text: "#F5EFEC",
  textDim: "#A89A93",
  border: "#2B2421",
  success: "#5BC489",
  warning: "#E8B14E",
};

export const spacing = { xs: 4, s: 8, m: 16, l: 24, xl: 32 };

export const trustTier = (score: number) =>
  score >= 90 ? "Excellent" : score >= 75 ? "Good" : "Building";
