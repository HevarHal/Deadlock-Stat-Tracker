import { formatDuration } from "./format.js";
const node = (tag, text, className) => {
  const element = document.createElement(tag);
  if (text != null) element.textContent = text;
  if (className) element.className = className;
  return element;
};

export function purchaseTimeline(items) {
  const groups = [];
  const events = items.flatMap((item) => [
    { ...item, sold: false },
    ...(item.soldTime > 0
      ? [{ ...item, time: item.soldTime, sold: true }]
      : []),
  ]);
  for (const item of events.sort((a, b) => a.time - b.time)) {
    const index = Math.floor(Math.max(0, item.time) / 300);
    while (groups.length <= index)
      groups.push({ start: groups.length * 300, items: [] });
    groups[index].items.push(item);
  }
  return groups;
}

function itemCard(item) {
  const card = node(
    "li",
    null,
    item.sold ? "build-item build-item-sold" : "build-item",
  );
  const label = `${item.sold ? "Sold" : "Bought"} ${item.name} at ${formatDuration(item.time)}`;
  card.setAttribute("aria-label", label);
  card.title = label;
  card.tabIndex = 0;
  if (item.image && /^https:\/\//.test(item.image)) {
    const image = node("img");
    image.src = item.image;
    image.alt = "";
    image.loading = "lazy";
    image.addEventListener("error", () => image.remove(), { once: true });
    card.append(image);
  }
  const text = node("div");
  text.append(node("strong", item.name));
  text.append(node("small", formatDuration(item.time)));
  card.append(text);
  return card;
}

function copyId(label, id) {
  const line = node("div", null, "build-id");
  const copy = node("button", "Copy");
  copy.type = "button";
  copy.setAttribute("aria-label", `Copy ${label.toLowerCase()} ${id}`);
  const feedback = node("span");
  feedback.setAttribute("role", "status");
  let feedbackTimer;
  copy.addEventListener("click", async () => {
    clearTimeout(feedbackTimer);
    try {
      await navigator.clipboard.writeText(String(id));
      feedback.textContent = "Copied!";
      feedbackTimer = setTimeout(() => {
        feedback.textContent = "";
      }, 1000);
    } catch {
      feedback.textContent =
        "Could not copy. Select the number to copy it manually.";
    }
  });
  line.append(node("span", `${label}: ${id}`), copy, feedback);
  return line;
}

function render(panel, data) {
  const matchId = copyId("Match ID", data.matchId);
  matchId.classList.add("match-id");
  panel.replaceChildren(node("h3", "Item timeline"));
  if (data.items.length) {
    const timeline = node("ol", null, "purchase-timeline");
    for (const group of purchaseTimeline(data.items).filter(
      (group) => group.items.length,
    )) {
      const period = node("li", null, "purchase-period");
      const items = node("ul", null, "build-items");
      items.append(...group.items.map((item) => itemCard(item)));
      period.append(items);
      period.append(
        node("h4", `${group.start / 60} - ${group.start / 60 + 5} min`),
      );
      timeline.append(period);
    }
    panel.append(timeline);
  } else
    panel.append(
      node("p", "No item purchases were available in this match’s metadata."),
    );
  panel.append(node("h3", "Starting build guide"));
  if (!data.guide) {
    panel.append(node("p", data.guideMessage), matchId);
    return;
  }
  const guide = data.guide;
  panel.append(node("h4", guide.name));
  if (guide.description) panel.append(node("p", guide.description));
  const identifiers = node("div", null, "match-build-identifiers");
  identifiers.append(copyId("Build ID", guide.id), matchId);
  panel.append(identifiers);
}

export function attachMatchBuild(row, match, account) {
  const details = node("tr", null, "match-build-row");
  details.hidden = true;
  const cell = node("td");
  cell.colSpan = 8;
  const panel = node("section", null, "match-build");
  panel.id = `match-build-${match.matchId}`;
  panel.setAttribute("aria-label", `Build details for match ${match.matchId}`);
  cell.append(panel);
  details.append(cell);
  const button = node("button", null, "match-toggle");
  button.type = "button";
  button.textContent = row.firstElementChild.textContent;
  button.setAttribute(
    "aria-label",
    `Show build details for ${match.heroName}, ${button.textContent}`,
  );
  button.setAttribute("aria-controls", panel.id);
  button.setAttribute("aria-expanded", "false");
  row.firstElementChild.replaceChildren(button);
  row.classList.add("expandable-match");
  let loaded = false,
    loading = false;
  async function load() {
    if (loaded || loading) return;
    loading = true;
    panel.setAttribute("aria-busy", "true");
    const status = node("p", "Loading items and starting guide…");
    status.setAttribute("role", "status");
    panel.replaceChildren(status);
    try {
      const response = await fetch(
        `/api/player/${encodeURIComponent(account)}/matches/${match.matchId}/build`,
      );
      const data = await response.json();
      if (!response.ok)
        throw Error(
          typeof data.detail === "string"
            ? data.detail
            : "Build details are unavailable.",
        );
      render(panel, data);
      loaded = true;
    } catch (error) {
      const retry = node("button", "Try again");
      retry.type = "button";
      retry.addEventListener("click", load);
      panel.replaceChildren(node("p", error.message), retry);
    } finally {
      loading = false;
      panel.removeAttribute("aria-busy");
    }
  }
  function toggle() {
    details.hidden = !details.hidden;
    button.setAttribute("aria-expanded", String(!details.hidden));
    if (!details.hidden) load();
  }
  button.addEventListener("click", toggle);
  row.addEventListener("click", (event) => {
    if (!event.target.closest("button, a")) toggle();
  });
  return details;
}
