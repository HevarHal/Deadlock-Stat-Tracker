import { formatNumber } from "./format.js";
import { applyHeroTheme } from "./hero-theme.js";
import { renderMatches, renderRank, tableAssets } from "./match-table.js";
import { matchingPlayers, playerPath, readPlayerRoute } from "./player-route.js";

const byId = (id) => document.getElementById(id);
// View state is transient; the player URL identifies the profile on refresh.
let account = "";
let scope = "all";
let page = 1;
let pages = 0;
let busy = false;
let heroes = [];
const catalog = fetch("/assets/heroes.json")
  .then((r) => r.json())
  .then((data) => {
    heroes = data;
  })
  .catch(() => {});
function renderProfileRank(badge) {
  byId("rank-label").textContent =
    scope === "all" ? "All-time highest rank" : "Season 1 current rank";
  byId("profile-rank").replaceChildren();
  renderRank(byId("profile-rank"), { mode: "Ranked", rankedBadge: badge });
  byId("profile-rank").title =
    scope === "all"
      ? "Highest rank in available match history"
      : "Latest reported rank within Season 1";
}
function clearStats() {
  for (const id of [
    "wins",
    "losses",
    "total",
    "souls",
    "unscored",
    "kd",
    "rate",
    "hero-games",
  ])
    byId(id).textContent = "—";
  byId("hero-name").textContent = "Most-played hero";
  byId("hero-art").hidden = true;
  byId("profile-rank").textContent = "—";
  renderMatches(byId("rows"), [], account);
}
clearStats();
byId("activity").textContent = "Search for a player to load their stats.";
byId("player-name").textContent = "Find your player.";
byId("player-id").textContent = "Search by Steam name or account ID";
byId("history-count").textContent = "No player selected";
byId("page-label").textContent = "Select a player to view matches";
let playerName = "";
async function fetchPlayerData(url) {
  const response = await fetch(url);
  if (!response.ok)
    throw Error(
      `Unable to load player data (${response.status}). Please try again.`,
    );
  return response.json();
}
function updateControls() {
  byId("previous").disabled = busy || page <= 1;
  byId("next").disabled = busy || page >= pages;
  document
    .querySelectorAll(".scope button, #search button")
    .forEach((b) => (b.disabled = busy));
}
async function renderSummary(stats) {
  const m = stats.metrics;
  if (!m) throw Error("Player summary is unavailable.");
  for (const [id, key] of Object.entries({
    wins: "wins",
    losses: "losses",
    total: "totalMatches",
    souls: "avgSoulsCollected",
    unscored: "unscored",
    kd: "killDeathRatio",
  }))
    byId(id).textContent = formatNumber(m[key]);
  byId("rate").textContent =
    m.winRatePercentage == null ? "—" : `${m.winRatePercentage}%`;
  const name =
    (scope === "all" ? m.overallMostPlayedHero : m.dominantHero) || "Unknown";

  byId("hero-name").textContent = name;
  byId("hero-games").textContent = formatNumber(
    scope === "all" ? m.overallMostPlayedHeroMatches : m.dominantHeroMatches,
  );
  byId("hero-scope").textContent =
    scope === "all"
      ? "MOST PLAYED HERO · ALL TIME"
      : "MOST PLAYED HERO · SEASON 1 RANKED";
  byId("player-name").textContent = playerName || `Player ${account}`;
  byId("player-id").textContent = `Steam account ID · ${account}`;
  await catalog;
  const hero = heroes.find(
    (h) =>
      h.name.toLowerCase() === String(name).toLowerCase() ||
      String(h.id) === String(name),
  );
  applyHeroTheme(name, hero?.image);
  byId("hero-art").hidden = !hero?.image;
  if (hero?.image) {
    byId("hero-art").dataset.fallback = hero.fallbackImage || "";
    byId("hero-art").src = new URL(hero.image, window.location.origin + "/").href;
    byId("hero-art").alt = `${hero.name}, this player's most-used hero`;
  }
}

async function loadPlayer(summary = true, preserveProfile = false) {
  if (!account || busy) return;
  busy = true;
  updateControls();
  byId("activity").textContent = "";
  byId("history").setAttribute("aria-busy", "true");
  const loadingRow = document.createElement("tr");
  const loadingCell = document.createElement("td");
  loadingCell.colSpan = 8;
  loadingCell.className = "history-loading";
  loadingCell.textContent = "Loading match history…";
  loadingRow.append(loadingCell);
  byId("rows").replaceChildren(loadingRow);
  byId("history-count").textContent = "Loading matches…";
  try {
    const [stats, history] = await Promise.all([
      summary
        ? fetchPlayerData(`/api/player/${account}/summary?scope=${scope}`)
        : null,
      fetchPlayerData(
        `/api/player/${account}/matches?scope=${scope}&page=${page}&page_size=5`,
      ),
    ]);
    if (stats) {
      await renderSummary(stats);
    }
    await tableAssets;
    renderProfileRank(
      scope === "all" ? history.highestRankBadge : history.rankBadge,
    );
    renderMatches(byId("rows"), history.matches, account);
    pages = history.totalPages;
    byId("history-count").textContent =
      `${formatNumber(history.totalMatches)} matches`;
    byId("page-label").textContent = pages
      ? `Page ${page} of ${pages}`
      : "No matches in this scope";
    byId("activity").textContent = "";
  } catch (error) {
    if (summary && !preserveProfile) clearStats();
    byId("activity").textContent = error.message;
    byId("rows").replaceChildren();
    byId("history-count").textContent = "Match history unavailable";
    pages = 0;
    byId("page-label").textContent = "Try loading the player again";
  } finally {
    busy = false;
    byId("history").removeAttribute("aria-busy");
    updateControls();
  }
}
byId("hero-art").addEventListener("error", () => {
  const image = byId("hero-art");
  if (image.dataset.fallback) {
    const fallback = image.dataset.fallback;
    delete image.dataset.fallback;
    image.src = fallback;
  } else image.hidden = true;
});
async function selectPlayer(id, name = "", avatar = "") {
  const path = playerPath(id, name);
  const entry = { account: String(id), playerName: name, avatar };
  if (window.location.pathname.replace(/\/$/, "") !== path) {
    window.history.pushState(entry, "", path);
  } else {
    window.history.replaceState(entry, "", path);
  }
  account = String(id);
  playerName = name;
  page = 1;
  const profileAvatar = byId("player-avatar");
  profileAvatar.hidden = !avatar;
  if (avatar) {
    profileAvatar.src = avatar;
    profileAvatar.alt = `${name || "Player"} Steam avatar`;
  } else profileAvatar.removeAttribute("src");
  byId("search-results").replaceChildren();
  clearStats();
  await loadPlayer();
}
async function searchPlayers(query, resolveRoute = false) {
  busy = true;
  updateControls();
  byId("activity").textContent = "Searching Steam players…";
  byId("search-results").replaceChildren();
  try {
    const result = await fetchPlayerData(
      `/api/player/search?query=${encodeURIComponent(query)}`,
    );
    const exact = matchingPlayers(result.players || [], query);
    if (resolveRoute && exact.length === 1) {
      busy = false;
      const player = exact[0];
      await selectPlayer(player.accountId, player.playerName, player.avatar);
      return;
    }
    for (const player of result.players || []) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `${player.playerName} · ${player.accountId}`;
      if (player.avatar) {
        const avatar = document.createElement("img");
        avatar.src = player.avatar;
        avatar.alt = "";
        avatar.className = "search-avatar";
        avatar.addEventListener("error", () => avatar.remove());
        button.prepend(avatar);
      }
      button.addEventListener("click", () => {
        if (!busy)
          selectPlayer(player.accountId, player.playerName, player.avatar);
      });
      byId("search-results").append(button);
    }
    let message = "No matching players found.";
    if (result.players?.length) {
      message = resolveRoute ? "Choose a player below to view their profile." : "";
    }
    byId("activity").textContent = message;
  } catch (error) {
    byId("activity").textContent = error.message;
  } finally {
    busy = false;
    updateControls();
  }
}
byId("search").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  const query = event.currentTarget.querySelector("input").value.trim();
  if (!query) return;
  if (/^\d+$/.test(query)) {
    await selectPlayer(query);
    return;
  }
  await searchPlayers(query);
});
document.querySelectorAll("[data-scope]").forEach((button) =>
  button.addEventListener("click", () => {
    if (busy) return;
    scope = button.dataset.scope;
    document
      .querySelectorAll("[data-scope]")
      .forEach((b) => b.classList.toggle("selected", b === button));
    page = 1;
    if (account) {
      loadPlayer(true, true);
    } else
      byId("rank-label").textContent =
        scope === "all" ? "All-time highest rank" : "Season 1 current rank";
  }),
);
byId("previous").addEventListener("click", () => {
  if (!busy && page > 1) {
    page--;
    loadPlayer(false);
  }
});
byId("next").addEventListener("click", () => {
  if (!busy && page < pages) {
    page++;
    loadPlayer(false);
  }
});
byId("player-avatar").addEventListener("error", () => {
  byId("player-avatar").hidden = true;
});

function fitPlayerName() {
  const name = byId("player-name");
  name.style.removeProperty("font-size");
  const available = name.clientWidth;
  if (!available) return;
  const base = parseFloat(getComputedStyle(name).fontSize);
  if (name.scrollWidth > available) {
    name.style.fontSize = `${((base * available) / name.scrollWidth) * 0.97}px`;
  }
}
let nameFitFrame;
function scheduleNameFit() {
  cancelAnimationFrame(nameFitFrame);
  nameFitFrame = requestAnimationFrame(fitPlayerName);
}
new ResizeObserver(scheduleNameFit).observe(
  document.querySelector(".player-identity"),
);
new MutationObserver(scheduleNameFit).observe(byId("player-name"), {
  childList: true,
  characterData: true,
  subtree: true,
});
new MutationObserver(scheduleNameFit).observe(byId("player-avatar"), {
  attributes: true,
  attributeFilter: ["hidden"],
});
document.fonts.ready.then(scheduleNameFit);

// Reload the selected route so Back/Forward also works during an active request.
window.addEventListener("popstate", () => window.location.reload());

async function restoreView() {
  const route = readPlayerRoute(window.location.pathname);
  if (route === null) return;
  const entry = window.history.state;
  if (entry?.account && (entry.playerName || entry.account) === route) {
    await selectPlayer(entry.account, entry.playerName, entry.avatar);
  } else if (/^\d+$/.test(route)) {
    await selectPlayer(route);
  } else {
    byId("search").querySelector("input").value = route;
    await searchPlayers(route, true);
  }
}
restoreView();
