import { formatNumber, formatDuration } from "./format.js";
import { attachMatchBuild } from "./match-build.js";

let portraits = [],
  ranks = [];
export const tableAssets = Promise.all(
  ["portraits", "ranks"].map((name) =>
    fetch(`assets/${name}.json`).then((r) => r.json()),
  ),
)
  .then(([p, r]) => {
    portraits = p.value || p;
    ranks = r.value || r;
  })
  .catch(() => {});
function portraitCell(td, match) {
  const hero = portraits.find(
    (h) => String(h.id) === String(match.heroId) || h.name === match.heroName,
  );
  if (!hero?.portrait) {
    td.textContent = match.heroName;
    return;
  }
  const image = document.createElement("img");
  image.src = hero.portrait;
  image.alt = match.heroName;
  image.title = match.heroName;
  image.className = "match-portrait";
  image.addEventListener("error", () => {
    td.textContent = match.heroName;
  });
  td.append(image);
}
export function renderRank(td, match) {
  if (match.mode !== "Ranked") {
    td.textContent = "—";
    return;
  }
  const badge = match.rankedBadge;
  const tier = Number.isInteger(badge) ? Math.floor(badge / 10) : -1;
  const subrank = badge % 10;
  const rank = ranks.find((r) => r.tier === tier);
  if (!rank || badge <= 0) {
    td.textContent = "Unavailable";
    td.title = "No rank was reported for this match";
    return;
  }
  const image = document.createElement("img");
  image.src =
    rank.images[`small_subrank${subrank}_webp`] || rank.images.small_webp;
  image.alt = `${rank.name}${subrank ? ` ${subrank}` : ""}`;
  image.title = image.alt;
  image.className = "match-rank";
  image.addEventListener("error", () => {
    td.textContent = image.alt;
  });
  td.append(image);
}
function textCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  return cell;
}

function matchRow(match) {
  const row = document.createElement("tr");
  const date = new Date(match.startTime * 1000).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  const hero = document.createElement("td");
  portraitCell(hero, match);
  const rank = document.createElement("td");
  renderRank(rank, match);
  const result = document.createElement("td");
  const badge = document.createElement("span");
  badge.className = "result";
  if (match.result === "Win") badge.classList.add("win");
  if (match.result === "Loss") badge.classList.add("loss");
  badge.textContent = match.result;
  result.append(badge);
  const kda = [match.kills, match.deaths, match.assists]
    .map(formatNumber)
    .join(" / ");
  row.append(
    textCell(date),
    hero,
    textCell(match.mode),
    rank,
    result,
    textCell(kda),
    textCell(formatNumber(match.souls)),
    textCell(formatDuration(match.durationSeconds)),
  );
  return row;
}

export function renderMatches(container, matches, account) {
  container.replaceChildren(
    ...matches.flatMap((match) => {
      const row = matchRow(match);
      return match.matchId == null
        ? [row]
        : [row, attachMatchBuild(row, match, account)];
    }),
  );
}
