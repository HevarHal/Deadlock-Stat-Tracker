export function playerPath(account, name = "") {
  return `/player/${encodeURIComponent(name || String(account))}`;
}

export function readPlayerRoute(pathname) {
  const match = /^\/player\/([^/]+)\/?$/.exec(pathname);
  if (!match) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return null;
  }
}

export function matchingPlayers(players, name) {
  return players.filter(
    (player) => player.playerName.toLowerCase() === name.toLowerCase(),
  );
}
