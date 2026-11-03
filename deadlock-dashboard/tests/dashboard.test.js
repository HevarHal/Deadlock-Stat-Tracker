import assert from "node:assert/strict";
import test from "node:test";
import { purchaseTimeline } from "../src/match-build.js";
import { formatDuration, formatNumber } from "../src/format.js";

test("timeline places purchases and sales at five-minute boundaries", () => {
  const items = [
    { id: 1, time: 299, soldTime: 600 },
    { id: 2, time: 300, soldTime: 0 },
  ];
  const groups = purchaseTimeline(items);
  assert.deepEqual(
    groups.map((group) => group.start),
    [0, 300, 600],
  );
  assert.equal(groups[0].items[0].sold, false);
  assert.equal(groups[1].items[0].id, 2);
  assert.deepEqual(
    [groups[2].items[0].id, groups[2].items[0].time, groups[2].items[0].sold],
    [1, 600, true],
  );
  assert.equal(items[0].time, 299);
  assert.deepEqual(purchaseTimeline([]), []);
});

test("formatting preserves zero values and handles missing match data", () => {
  assert.equal(formatNumber(0), "0");
  assert.equal(formatNumber(null), "\u2014");
  assert.equal(formatDuration(null), "\u2014");
  assert.equal(formatDuration(0), "0:00");
  assert.equal(formatDuration(1801), "30:01");
});
