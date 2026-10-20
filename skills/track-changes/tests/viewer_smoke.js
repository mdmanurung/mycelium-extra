// node viewer_smoke.js report.html: runs the page's viewer.js against a minimal DOM stub and clicks every
// control it draws (tabs, filters, entries, evidence links, copy buttons). Not a browser: it catches runtime
// errors and checks that the page draws text only through textContent. A real file:// check is still advised.
"use strict";
const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const data = /<script type="application\/json" id="data">([\s\S]*?)<\/script>/.exec(html)[1];
const code = /<\/script>\s*<script>([\s\S]*?)<\/script>/.exec(html)[1];

class El {
  constructor(tag) { this.tag = tag; this.children = []; this.listeners = {}; this.style = {}; this.dataset = {}; this.className = ""; this._text = ""; this.value = ""; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(""); }
  appendChild(c) { this.children.push(c); return c; }
  removeChild(c) { this.children.splice(this.children.indexOf(c), 1); return c; }
  get firstChild() { return this.children[0] || null; }
  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  setAttribute(k, v) { this.attrs = this.attrs || {}; this.attrs[k] = String(v); }
  removeAttribute(k) { if (this.attrs) delete this.attrs[k]; }
  setSelectionRange() {} focus() {} select() {}
  get selectionStart() { return 0; }
}
const byId = {data: Object.assign(new El("script"), {_text: data}), app: new El("div")};
const body = new El("body");
global.window = {isSecureContext: false};
Object.defineProperty(global, "navigator", {value: {}, configurable: true});
global.document = {
  getElementById: id => byId[id] || null, createElement: t => new El(t), createTextNode: t => Object.assign(new El("#text"), {_text: t}),
  querySelector: () => null, body, documentElement: new El("html"), execCommand: () => true, title: "",
};

let copied = [];
document.execCommand = () => { copied.push(document.lastCopy); return true; };
global.setTimeout = () => 0; global.clearTimeout = () => {};

new Function(code)();
const payload = JSON.parse(data);
if (payload.journal) {
  const walk = el => [el].concat(...el.children.map(walk));
  const nodes = cls => walk(byId.app).filter(e => e.className.split(" ").includes(cls));
  const click = e => { if (!e) throw Error("missing control"); (e.listeners.click || []).forEach(f => f()); };
  const button = prefix => walk(byId.app).find(e => e.tag === "button" && e.textContent.startsWith(prefix));
  if (nodes("journal-concern").length > 3 || nodes("journal-event").length) throw Error("overview budget exceeded");
  if (!byId.app.textContent.includes("Coverage:")) throw Error("coverage hidden");
  const original = byId.data.textContent;
  const first = nodes("journal-concern")[0];
  if (first) {
    click(first);
    if (!nodes("journal-detail").length) throw Error("concern does not reveal detail");
    if (!walk(byId.app).some(e => e.tag === "summary" && e.textContent.startsWith("Evidence and provenance"))) throw Error("missing evidence disclosure");
    click(button("Back to overview"));
  }
  click(button("Show all "));
  const count = nodes("journal-concern").length;
  if (count < (first ? 1 : 0)) throw Error("concerns lost");
  click(button("Back to overview")); click(button("Explore history"));
  const target = payload.journal.events.filter(e => e.kind === "attempt" && e.summary === "exit 0 recorded").pop();
  const search = walk(byId.app).find(e => e.tag === "input" && e.type === "search");
  search.value = target.id; search.listeners.input.forEach(f => f());
  if (nodes("journal-event").length !== 1) throw Error("search missed loaded, collapsed record");
  click(nodes("journal-event")[0]);
  if (!nodes("journal-detail")[0].textContent.includes(target.id)) throw Error("wrong search selection");
  click(button("Collapse detail")); click(button("Expand detail"));
  click(button("Back to overview")); click(button("Explore history"));
  const restored = walk(byId.app).find(e => e.tag === "input" && e.type === "search");
  if (restored.value !== target.id) throw Error("search context lost");
  if (byId.data.textContent !== original) throw Error("presentation changed exported evidence");
  console.log("OK journal events=" + payload.journal.events.length + " concerns=" + count);
} else {
// the first draw is the Review view: its filters sit directly under the view tabs, not beside them
const order = byId.app.children.map(c => c.className.split(" ")[0]);
const v = order.indexOf("views"), f = order.indexOf("filters");
if (v < 0 || f !== v + 1) throw new Error("filters must sit directly under the view tabs, got: " + order.join(","));
const clickable = el => [].concat(el.listeners.click ? [el] : [], ...el.children.map(clickable));
let clicks = 0;
for (let round = 0; round < 3; round++) {
  for (const el of clickable(byId.app).slice()) { for (const fn of el.listeners.click) { fn(); clicks++; } }
}
const text = byId.app.textContent;

if (!text.includes("Track changes")) throw new Error("page did not draw");
if (clicks < 10) throw new Error("too few controls clicked: " + clicks);
console.log("OK clicks=" + clicks + " items=" + payload.items.length + " chars=" + text.length);

}
