import palettes from "./hero-palettes.json";

// Colors sampled from each render's outer scenery, not the hero's costume.
export function applyHeroTheme(name, image = "") {
  const [surface, accent] = palettes[name] || ["#181c24", "#b6cbbd"];
  const style = document.documentElement.style;
  style.setProperty("--hero-surface", surface);
  style.setProperty("--hero-accent", accent);
  const url = image ? new URL(image, location.origin + "/").href : "";
  style.setProperty("--hero-backdrop", url ? `url("${url}")` : "none");
}
