import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = (await readFile(new URL("../src/match-build.js", import.meta.url), "utf8"))
  .replace(/^import .*;\r?\n/gm, "").replaceAll("export function", "function");

test("only IDs resolved to guides are visible and copyable", () => {
  const element = () => ({
    children: [], classList: { add() {} }, attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; },
    addEventListener() {},
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
  });
  const context = vm.createContext({ document: { createElement: element } });
  vm.runInContext(source, context);
  const collect = (node) => [node, ...node.children.flatMap(collect)];
  for (const data of [
    { buildId: 999, guide: null, guideMessage: "Guide lookup failed." },
    { buildId: null, guide: null, guideMessage: "No guide recorded." },
    { buildId: 999, guide: { id: 999, name: "Example guide" } },
  ]) {
    context.panel = element();
    context.data = { items: [], matchId: 100, ...data };
    vm.runInContext("render(panel, data)", context);
    const nodes = collect(context.panel);
    assert.equal(nodes.filter((node) => node.textContent === "Build ID: 999").length, data.guide ? 1 : 0);
    assert.equal(nodes.some((node) => node.attributes["aria-label"] === "Copy build id 999"), Boolean(data.guide));
    assert.ok(nodes.some((node) => node.textContent === "Match ID: 100"));
    if (data.guideMessage) assert.ok(nodes.some((node) => node.textContent === data.guideMessage));
  }
});
