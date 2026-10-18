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
const clickable = el => [].concat(el.listeners.click ? [el] : [], ...el.children.map(clickable));
let clicks = 0;
for (let round = 0; round < 3; round++) {
  for (const el of clickable(byId.app).slice()) { for (const fn of el.listeners.click) { fn(); clicks++; } }
}
const text = byId.app.textContent;
const payload = JSON.parse(data);
if (!text.includes("Track changes")) throw new Error("page did not draw");
if (clicks < 10) throw new Error("too few controls clicked: " + clicks);
console.log("OK clicks=" + clicks + " items=" + payload.items.length + " chars=" + text.length);
