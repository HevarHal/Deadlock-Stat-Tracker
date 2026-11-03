import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import { matchingPlayers, playerPath, readPlayerRoute } from "../src/player-route.js";

const source = (await readFile(new URL("../src/profile-app.js", import.meta.url), "utf8"))
  .replace(/^import .*;\r?\n/gm, "")
  .replace(/restoreView\(\);\s*$/, "globalThis.ready = restoreView();");

// Run the real controller with a small DOM and API fixture. No browser storage
// or history state survives between instances, as with a newly opened link.
async function openPage(pathname, players) {
  const nodes = new Map();
  function node(key) {
    if (!nodes.has(key)) {
      const attributes = new Map();
      nodes.set(key, {
        textContent: "", value: "", children: [], listeners: {}, dataset: {},
        style: { removeProperty() {} }, classList: { toggle() {} },
        addEventListener(event, callback) { this.listeners[event] = callback; },
        replaceChildren(...children) { this.children = children; },
        append(child) { this.children.push(child); }, prepend() {},
        querySelector: (selector) => node(`${key} ${selector}`),
        setAttribute: (name, value) => attributes.set(name, value),
        getAttribute: (name) => attributes.get(name),
        removeAttribute: (name) => attributes.delete(name),
      });
    }
    return nodes.get(key);
  }
  const calls = [];
  let storageReads = 0;
  const location = { pathname, origin: "https://deadlocktracker.ca" };
  const history = {
    state: null,
    pushState(state, _, path) { this.state = state; location.pathname = path; },
    replaceState(state, _, path) { this.state = state; location.pathname = path; },
  };
  const context = vm.createContext({
    URL, matchingPlayers, playerPath, readPlayerRoute,
    formatNumber: (value) => String(value ?? ""),
    applyHeroTheme() {}, renderRank() {}, renderMatches() {},
    tableAssets: Promise.resolve(),
    ResizeObserver: class { observe() {} },
    MutationObserver: class { observe() {} },
    requestAnimationFrame() {}, cancelAnimationFrame() {},
    document: {
      getElementById: node, querySelector: node, querySelectorAll: () => [],
      createElement: (tag) => node(Symbol(tag)), fonts: { ready: Promise.resolve() },
    },
    window: {
      location, history, addEventListener() {},
      get sessionStorage() { storageReads++; throw Error("Storage blocked"); },
    },
    fetch: async (url) => {
      calls.push(url);
      let data;
      if (url === "/assets/heroes.json") data = [];
      else if (url.startsWith("/api/player/search?")) data = { players };
      else if (url.includes("/summary?")) data = { metrics: { wins: 12 } };
      else if (url.includes("/matches?"))
        data = { matches: [], totalPages: 1, totalMatches: 12 };
      else throw Error(`Unexpected request: ${url}`);
      return { ok: true, json: async () => data };
    },
  });
  vm.runInContext(source, context);
  await context.ready;
  return { node, calls, location, context, storageReads: () => storageReads };
}

const player = { accountId: "123", playerName: "Player One" };

test("search selection and refresh load the same player with session storage blocked", async () => {
  const first = await openPage("/", [player]);
  first.node("search input").value = "Player One";
  await first.node("search").listeners.submit({
    preventDefault() {}, currentTarget: first.node("search"),
  });
  assert.equal(first.node("search-results").children.length, 1);
  // Await the controller directly; the click listener starts this same action.
  await vm.runInContext('selectPlayer("123", "Player One")', first.context);
  assert.equal(first.location.pathname, "/player/Player%20One");
  assert.equal(first.node("player-name").textContent, "Player One");
  vm.runInContext('scope = "season1"; page = 3;', first.context);

  const refreshed = await openPage(first.location.pathname, [player]);
  assert.equal(refreshed.node("player-name").textContent, "Player One");
  assert.equal(refreshed.node("wins").textContent, "12");
  assert.ok(refreshed.calls.includes("/api/player/search?query=Player%20One"));
  assert.ok(refreshed.calls.includes("/api/player/123/summary?scope=all"));
  assert.ok(refreshed.calls.includes("/api/player/123/matches?scope=all&page=1&page_size=5"));
  assert.equal(first.storageReads(), 0);
  assert.equal(refreshed.storageReads(), 0);
});

test("duplicate names require a selection rather than loading an arbitrary account", async () => {
  const page = await openPage("/player/Player%20One", [
    player, { ...player, accountId: "456" },
  ]);
  assert.equal(page.node("search-results").children.length, 2);
  assert.equal(page.calls.some((url) => url.includes("/summary?")), false);
  assert.equal(page.node("activity").textContent, "Choose a player below to view their profile.");
});
