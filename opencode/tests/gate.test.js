/**
 * Run: node --test opencode/tests/
 *
 * The adapter's own logic (helpers, handler wiring, the spawn contract against the real
 * Python launcher). Gate semantics belong to hooks/tests/test_opencode_gate.py; these tests
 * check what the JS layer adds: payload shapes, replies turned into throws/appends, and
 * inertness without a gate.
 */
import test from "node:test"
import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
import plugin, { __test__ } from "../index.js"

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = dirname(dirname(HERE))
const PATHS = { py: join(ROOT, "hooks", "py.sh"), gate: join(ROOT, "hooks", "gate_run.py") }

function pythonAtLeast39() {
  const names = [process.env.MYCELIUM_EXTRA_PYTHON, "python3", "python3.14", "python3.13",
    "python3.12", "python3.11", "python3.10", "python3.9"].filter(Boolean)
  for (const name of names) {
    const probe = spawnSync(name, ["-c", "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"])
    if (probe.status === 0) return name
  }
  return null
}

const PYTHON = pythonAtLeast39()
if (PYTHON) process.env.MYCELIUM_EXTRA_PYTHON = PYTHON // py.sh reads it; 3.6-only nodes then still run the tests

function gatedRepo() {
  const dir = mkdtempSync(join(tmpdir(), "mx-opencode-"))
  mkdirSync(join(dir, ".mycelium-extra"), { recursive: true })
  writeFileSync(join(dir, ".mycelium-extra", "gate.json"), "{}")
  return dir
}

function fakeCtx(location, stream) {
  const handlers = { before: [], after: [], prompt: [], commands: [] }
  const calls = { prompt: [], synthetic: [] }
  const noop = async () => {}
  const ctx = {
    options: {},
    location: { directory: location },
    tool: { hook: async (name, callback) => {
      ;(name === "execute.before" ? handlers.before : handlers.after).push(callback)
    } },
    command: { transform: async (callback) => {
      callback({ add: (definition) => handlers.commands.push(definition) })
    } },
    session: {
      hook: async (name, callback) => { if (name === "prompt") handlers.prompt.push(callback) },
      prompt: async (input) => calls.prompt.push(input),
      synthetic: async (input) => calls.synthetic.push(input),
      wait: noop,
    },
    event: stream || { subscribe: async function* () {} },
  }
  return { ctx, handlers, calls }
}

/** A controllable event stream: push() wakes the plugin's for-await loop. */
function streamCtx() {
  const queue = []
  let wake = null
  return {
    push(event) {
      queue.push(event)
      if (wake) {
        const resume = wake
        wake = null
        resume()
      }
    },
    subscribe: async function* () {
      for (;;) {
        while (queue.length) yield queue.shift()
        await new Promise((resolve) => { wake = resolve })
      }
    },
  }
}

async function waitFor(predicate, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (predicate()) return true
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  return predicate()
}

test("findRoot walks up to the gate directory", () => {
  const repo = gatedRepo()
  const sub = join(repo, "analysis", "deep")
  mkdirSync(sub, { recursive: true })
  assert.equal(__test__.findRoot(sub), repo)
  assert.equal(__test__.findRoot(mkdtempSync(join(tmpdir(), "mx-plain-"))), null)
})

test("helpers turn gate replies into host behavior", () => {
  const deny = { hookSpecificOutput: { permissionDecision: "deny", permissionDecisionReason: "mycelium-extra: no plan" } }
  assert.equal(__test__.denyReason(deny), "mycelium-extra: no plan")
  assert.equal(__test__.denyReason(null), null)
  assert.equal(__test__.contentText([{ type: "text", text: "a" }, { type: "file", uri: "x" }]), "a")
  assert.deepEqual(__test__.appendContent({ content: "a" }, "b"), { content: "a\n\nb" })
  assert.deepEqual(__test__.appendContent({}, "b"), { content: "b" })
  assert.deepEqual(__test__.appendContent({ content: [{ type: "text", text: "a" }] }, "b"),
    { content: [{ type: "text", text: "a" }, { type: "text", text: "b" }] })
  assert.match(__test__.blockedPromptText("done"), /handled the user's message/)
  assert.match(__test__.blockedPromptText("done"), /done/)
})

test("server events resolve session id and text from data or the flat shape", () => {
  assert.deepEqual(__test__.textEnded({ type: "session.text.ended", data: { sessionID: "s1", text: "hi" } }),
    { sessionID: "s1", text: "hi" })
  assert.deepEqual(__test__.textEnded({ type: "session.text.ended", sessionID: "s2", text: "old" }),
    { sessionID: "s2", text: "old" })
  assert.equal(__test__.textEnded({ type: "session.idle", data: { sessionID: "s1" } }), null)
  assert.equal(__test__.idleSession({ type: "session.idle", data: { sessionID: "s1" } }), "s1")
  assert.equal(__test__.idleSession({ type: "session.idle", sessionID: "s2" }), "s2")
  assert.equal(__test__.idleSession({ type: "session.text.ended", data: { sessionID: "s1" } }), null)
  assert.equal(__test__.eventLocation({ location: { directory: "/a" } }), "/a")
  assert.equal(__test__.eventLocation({}), null)
  assert.equal(__test__.samePlace("/a", "/a"), true)
  assert.equal(__test__.executionEnded({ type: "session.execution.succeeded", data: { sessionID: "s1" } }), "s1")
  assert.equal(__test__.executionEnded({ type: "session.execution.failed", sessionID: "s2" }), "s2")
  assert.equal(__test__.executionEnded({ type: "session.execution.started", data: { sessionID: "s1" } }), null)
  assert.equal(__test__.executionEnded({ type: "session.idle", data: { sessionID: "s1" } }), null)
})

test("the server-wide event stream is filtered to this location", async (t) => {
  if (!PYTHON) return t.skip("needs python3.9+")
  const repo = gatedRepo()
  const stream = streamCtx()
  const { ctx, calls } = fakeCtx(repo, stream)
  await plugin.setup(ctx)
  const plan = "## Plan\n| 1 | run `analysis/x.py` | repo | check |\n\nPlan status: READY"
  // A foreign location's turn: its text carries the other location, its end event carries no
  // location at all (the 2.0.32 shape), and neither may reach the gate.
  stream.push({ type: "session.text.ended", location: { directory: "/somewhere/else" },
    data: { sessionID: "foreign", text: plan } })
  stream.push({ type: "session.execution.succeeded", data: { sessionID: "foreign" } })
  // Our session: the text is captured from its location, the location-less end event then stops.
  stream.push({ type: "session.text.ended", location: { directory: repo },
    data: { sessionID: "mine", text: plan } })
  stream.push({ type: "session.execution.succeeded", data: { sessionID: "mine" } })
  assert.equal(await waitFor(() => calls.synthetic.length > 0, 20000), true, "no stop ran for the in-scope session")
  assert.equal(calls.synthetic.every((message) => message.sessionID === "mine"), true,
    "a foreign session produced a notification")
  assert.match(calls.synthetic[0].text, /approve plan/)
  assert.deepEqual(calls.prompt, [])
})

test("gateCwd prefers a cwd under a gate and falls back to the location", () => {
  const repo = gatedRepo()
  const sub = join(repo, "analysis")
  mkdirSync(sub, { recursive: true })
  const plain = mkdtempSync(join(tmpdir(), "mx-plain-"))
  assert.equal(__test__.gateCwd(sub, plain), sub)
  // a shell workdir outside every gate must not switch the location's gate off
  assert.equal(__test__.gateCwd(plain, repo), repo)
  assert.equal(__test__.gateCwd(plain, plain), null)
  assert.equal(__test__.gateCwd("", repo), repo)
})

test("skill commands come from the skills folder", () => {
  const skills = __test__.skillCommands(ROOT)
  assert.equal(skills.length, 13)
  const ids = skills.map((skill) => skill.id)
  for (const id of ["grill", "init", "verify", "handoff", "plan-review", "focus", "track-changes"]) assert.ok(ids.includes(id), id)
  assert.match(skills.find((skill) => skill.id === "grill").description, /planning/i)
  assert.equal(__test__.skillCommands("/nonexistent").length, 0)
  assert.match(__test__.commandText(ROOT, "verify", "status"), /skills\/verify/)
  assert.match(__test__.commandText(ROOT, "verify", "status"), /status/)
})

test("command entry points submit the skill with the user's request", async () => {
  const { ctx, handlers, calls } = fakeCtx(mkdtempSync(join(tmpdir(), "mx-plain-")))
  await plugin.setup(ctx)
  const names = handlers.commands.map((command) => command.name)
  assert.ok(names.includes("mycelium-extra:grill"), "names: " + names.slice(0, 3).join(", "))
  assert.ok(names.includes("mycelium-extra:verify"))
  const grill = handlers.commands.find((command) => command.name === "mycelium-extra:grill")
  assert.match(grill.description, /planning/i)
  await grill.execute({ sessionID: "s1", prompt: { text: "plan a QC redo" }, delivery: "steer" })
  assert.equal(calls.prompt.length, 1)
  assert.match(calls.prompt[0].text, /skill tool/)
  assert.match(calls.prompt[0].text, /`grill`/)
  assert.match(calls.prompt[0].text, /plan a QC redo/)
  assert.equal(calls.prompt[0].sessionID, "s1")
})

test("handlers block covered runs and leave other tools alone", async (t) => {
  if (!PYTHON) return t.skip("needs python3.9+")
  const { ctx, handlers } = fakeCtx(gatedRepo())
  await plugin.setup(ctx)
  assert.equal(handlers.before.length, 1)
  assert.equal(handlers.after.length, 1)
  assert.equal(handlers.prompt.length, 1)
  await assert.rejects(
    handlers.before[0]({ tool: "shell", input: { command: "python analysis/x.py" }, sessionID: "s", id: "c1" }),
    /mycelium-extra/)
  await handlers.before[0]({ tool: "read", input: { path: "README.md" }, sessionID: "s", id: "c2" })
})

test("an ungated repository stays inert", async () => {
  const { ctx, handlers } = fakeCtx(mkdtempSync(join(tmpdir(), "mx-plain-")))
  await plugin.setup(ctx)
  await handlers.before[0]({ tool: "shell", input: { command: "python analysis/x.py" }, sessionID: "s", id: "c1" })
  const prompt = { text: "approve plan abcd1234" }
  await handlers.prompt[0]({ prompt, sessionID: "s" })
  assert.equal(prompt.text, "approve plan abcd1234")
})

test("gate context is appended and a blocked prompt is rewritten", async (t) => {
  if (!PYTHON) return t.skip("needs python3.9+")
  const { ctx, handlers } = fakeCtx(gatedRepo())
  await plugin.setup(ctx)
  const appended = { text: "approve plan abcd1234" }
  await handlers.prompt[0]({ prompt: appended, sessionID: "s" })
  assert.match(appended.text, /Nothing was approved/)
  const blocked = { text: "card abcd1234" }
  await handlers.prompt[0]({ prompt: blocked, sessionID: "s" })
  assert.match(blocked.text, /handled the user's message/)
  assert.match(blocked.text, /no pending plan abcd1234/)
})

test("the spawn contract drives deny, approve, receipts, and inertness", async (t) => {
  if (!PYTHON) return t.skip("needs python3.9+")
  const repo = gatedRepo()
  const bash = { tool_name: "shell", tool_input: { command: "python analysis/x.py" }, cwd: repo,
    session_id: "s", tool_use_id: "c1" }
  const denied = await __test__.runGate(PATHS, "tool", bash, 10000)
  assert.equal(__test__.denyReason(denied) !== null, true)
  const plan = "## Plan\n| 1 | run `analysis/x.py` | repo | check |\n\nPlan status: READY"
  const notice = await __test__.runGate(PATHS, "stop", { last_assistant_message: plan, cwd: repo, session_id: "s" }, 30000)
  const hash = notice.systemMessage.split("approve plan ")[1].slice(0, 8)
  const approved = await __test__.runGate(PATHS, "prompt", { prompt: "approve plan " + hash, cwd: repo, session_id: "s" }, 10000)
  assert.match(approved.systemMessage, /approved/)
  assert.equal(await __test__.runGate(PATHS, "tool", bash, 10000), null)
  await __test__.runGate(PATHS, "post", { ...bash, status: "completed", tool_response: { content: "ok" } }, 20000)
  await __test__.runGate(PATHS, "post", { ...bash, status: "completed",
    tool_response: { metadata: { status: "completed", exit: 5 }, output: { exit: 5 }, content: [] } }, 20000)
  const receipts = readFileSync(join(repo, ".mycelium-extra", "receipts.jsonl"), "utf8")
    .trim().split("\n").map((line) => JSON.parse(line))
  assert.equal(receipts.length, 2)
  assert.equal(receipts[0].host, "opencode")
  assert.equal(receipts[0].exit_status, "unknown") // no code in that result
  assert.equal(receipts[1].exit_status, 5)        // the shell tool's metadata.exit, mapped
  assert.equal(receipts[1].exit_source, "response")
  const plain = mkdtempSync(join(tmpdir(), "mx-plain-"))
  assert.equal(await __test__.runGate(PATHS, "tool", { ...bash, cwd: plain }, 10000), null)
})
