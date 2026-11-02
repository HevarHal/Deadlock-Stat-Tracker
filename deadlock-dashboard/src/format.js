export function formatNumber(value) {
  return value == null ? "\u2014" : Number(value).toLocaleString();
}

export function formatDuration(seconds) {
  if (seconds == null) return "\u2014";
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}
