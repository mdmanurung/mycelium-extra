// node viewer_states.js report.html [label ...]: draws the page in the same DOM stub as viewer_smoke.js, then prints
// one JSON line per step: the page text, every status pill as [class, word], and the count of old `dot` markers.
// Each extra argument is the start of a button label (a view tab, say) to click before the next line.
// Not a browser: it shows what the viewer says, not how it looks.
"use strict";
const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const data = /<script type="application\/json" id="data">([\s\S]*?)<\/script>/.exec(html)[1];
const code = /<\/script>\s*<script>([\s\S]*?)<\/script>/.exec(html)[1];

class El {
  constructor(tag) { this.tag = tag; this.children = []; this.listeners = {}; this.dataset = {}; this.className = ""; this._text = ""; this.value = ""; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(""); }
  appendChild(c) { this.children.push(c); return c; }
  removeChild(c) { this.children.splice(this.children.indexOf(c), 1); return c; }
  get firstChild() { return this.children[0] || null; }
  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  setAttribute(k, v) { this.attrs = this.attrs || {}; this.attrs[k] = String(v); }
  removeAttribute(k) { if (this.attrs) delete this.attrs[k]; }
  focus() {} select() {}
}
const byId = {data: Object.assign(new El("script"), {_text: data}), app: new El("div")};
global.window = {isSecureContext: false};
Object.defineProperty(global, "navigator", {value: {}, configurable: true});
global.document = {
  getElementById: id => byId[id] || null, createElement: t => new El(t), createTextNode: t => Object.assign(new El("#text"), {_text: t}),
  body: new El("body"), documentElement: new El("html"), execCommand: () => true, title: "",
};
global.setTimeout = () => 0;
new Function(code)();

const walk = el => [el].concat(...el.children.map(walk));
const has = (e, cls) => e.className.split(" ").includes(cls);
function report() {
  const nodes = walk(byId.app);
  const pills = nodes.filter(e => has(e, "pill")).map(e => [e.className, e.textContent]);
  const attrs = (e, k) => (e.attrs || {})[k];
  const views = nodes.filter(e => has(e, "view")).map(e => [attrs(e, "aria-pressed"), attrs(e, "role")]);
  const roles = nodes.map(e => attrs(e, "role")).filter(Boolean);
  const scrollers = nodes.filter(e => attrs(e, "tabindex") === "0" && attrs(e, "aria-label")).map(e => e.className || e.tag);
  const theme = nodes.find(e => e.tag === "button" && e.textContent === "Light / dark");
  console.log(JSON.stringify({text: byId.app.textContent, pills, dots: nodes.filter(e => has(e, "dot")).length,
    views, roles, scrollers, themePressed: theme && attrs(theme, "aria-pressed"), live: nodes.some(e => attrs(e, "aria-live") === "polite")}));
}
report();
for (const label of process.argv.slice(3)) {
  const target = walk(byId.app).find(e => e.tag === "button" && e.textContent.startsWith(label));
  if (!target) throw Error("no button starting with " + label);
  target.listeners.click.forEach(f => f());
  report();
}
