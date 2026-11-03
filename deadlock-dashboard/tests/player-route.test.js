import assert from "node:assert/strict";
import test from "node:test";
import { matchingPlayers, playerPath, readPlayerRoute } from "../src/player-route.js";

test("player names round-trip through a single URL segment", () => {
  for (const name of ["Player One", "a/b?#%", "玩家", "CoolName"]) {
    const path = playerPath("123", name);
    assert.equal(readPlayerRoute(path), name);
    assert.equal(readPlayerRoute(`${path}/`), name);
  }
  assert.equal(playerPath("123", "CoolName"), "/player/CoolName");
  assert.equal(playerPath("123"), "/player/123");
  assert.equal(readPlayerRoute("/"), null);
  assert.equal(readPlayerRoute("/player/bad%escape"), null);
  assert.equal(readPlayerRoute("/player/name/extra"), null);
});

test("shared name links distinguish exact names and detect duplicate names", () => {
  const players = [
    { accountId: "1", playerName: "CoolName" },
    { accountId: "2", playerName: "CoolName Fan" },
  ];
  assert.deepEqual(matchingPlayers(players, "coolname"), [players[0]]);
  assert.deepEqual(matchingPlayers(players, "Missing"), []);
  players.push({ accountId: "3", playerName: "COOLNAME" });
  assert.equal(matchingPlayers(players, "CoolName").length, 2);
});
