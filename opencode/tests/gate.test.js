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
import { createHash } from "node:crypto"
import { existsSync, mkdirSync, mkdtempSync, readFileSync, utimesSync, writeFileSync } from "node:fs"
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

/** A gated repo with one exploratory run recorded for session "mine". */
function noticeRepo() {
  const repo = gatedRepo()
  writeFileSync(join(repo, ".mycelium-extra", "explore.log"),
    JSON.stringify({ session_id: "mine", command: "python analysis/explore.py" }) + "\n")
  return repo
}

/** A gated repo where the gate's own state says a script that session wrote still has open findings. */
function openLintRepo() {
  const repo = gatedRepo()
  writeFileSync(join(repo, ".mycelium-extra", "gate.json"), JSON.stringify({ lint_before_stop: true }))
  const rel = "analysis/check.R"
  const file = join(repo, rel)
  mkdirSync(dirname(file), { recursive: true })
  writeFileSync(file, "x <- 1\n")
  const when = 1700000000 // an exact mtime: the gate compares the recorded mtime literally
  utimesSync(file, when, when)
  const dir = join(repo, ".mycelium-extra", "pending", "mine.lint")
  mkdirSync(dir, { recursive: true })
  writeFileSync(join(dir, createHash("sha256").update(rel).digest("hex").slice(0, 16) + ".json"),
    JSON.stringify({ file: rel, rows: ["R001 magic number"], mtime: when }))
  return repo
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

test("a silent successful gate run is an allow, not a failure", async () => {
  // hooks/gate.py prints nothing when it has no objection; only a non-zero exit or a
  // signal means the gate did not run.
  const dir = mkdtempSync(join(tmpdir(), "mx-silent-"))
  const allow = join(dir, "allow.sh")
  const crash = join(dir, "crash.sh")
  writeFileSync(allow, "#!/bin/sh\nexit 0\n")
  writeFileSync(crash, "#!/bin/sh\nexit 3\n")
  assert.deepEqual(await __test__.runGate({ py: allow, gate: "unused" }, "tool", {}, 5000), {})
  assert.equal(await __test__.runGate({ py: crash, gate: "unused" }, "tool", {}, 5000), null)
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

test("a stop notice reaches the model as a synthetic message, with the gate's own text", async (t) => {
  if (!PYTHON) return t.skip("needs python3.9+")
  // Two fresh repos with the same state: one is driven through the plugin, the other is asked
  // directly for the reply the plugin had to deliver. The gate consumes the notice it reports,
  // so the two cannot share a repo.
  const driven = noticeRepo()
  const asked = noticeRepo()
  const stream = streamCtx()
  const { ctx, calls } = fakeCtx(driven, stream)
  await plugin.setup(ctx)
  const reply = await __test__.runGate({ ...PATHS, root: ROOT }, "stop",
    { last_assistant_message: "done", cwd: asked, session_id: "mine" }, 30000)
  assert.match(reply.systemMessage || "", /exploratory run\(s\) this session are not reportable/)
  assert.notEqual(reply.decision, "block")
  stream.push({ type: "session.text.ended", location: { directory: driven }, data: { sessionID: "mine", text: "done" } })
  stream.push({ type: "session.execution.succeeded", data: { sessionID: "mine" } })
  assert.equal(await waitFor(() => calls.synthetic.length > 0, 30000), true,
    "the Stop notice never reached the model")
  assert.deepEqual(calls.synthetic, [{ sessionID: "mine", text: reply.systemMessage }])
  assert.deepEqual(calls.prompt, [], "a notice must not be delivered as a steering prompt")
})

test("a blocked stop steers the model instead of notifying it", async (t) => {
  if (!PYTHON) return t.skip("needs python3.9+")
  const repo = openLintRepo()
  const stream = streamCtx()
  const { ctx, calls } = fakeCtx(repo, stream)
  await plugin.setup(ctx)
  stream.push({ type: "session.text.ended", location: { directory: repo }, data: { sessionID: "mine", text: "done" } })
  stream.push({ type: "session.execution.succeeded", data: { sessionID: "mine" } })
  assert.equal(await waitFor(() => calls.prompt.length > 0, 30000), true, "the Stop block never reached the model")
  assert.match(calls.prompt[0].text, /scilintr findings are still open/)
  assert.equal(calls.prompt[0].delivery, "steer")
  assert.deepEqual(calls.synthetic, [], "a blocking stop must not be delivered as a user-only notice")
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

test("an open focus line reaches the prompt even beside a hint", () => {
  const focus = "mycelium-extra focus: analysis/a. Stay on this analysis."
  const hint = { systemMessage: "mycelium-extra hint: this fits /mycelium-extra:handoff",
                 hookSpecificOutput: { additionalContext: "mycelium-extra hint: long text\n" + focus } }
  assert.equal(__test__.promptMessage(hint), hint.systemMessage + "\n" + focus)
  assert.equal(__test__.promptMessage({ hookSpecificOutput: { additionalContext: focus } }), focus)  // no hint: the context itself
  assert.equal(__test__.promptMessage({ systemMessage: "plain" }), "plain")
  assert.equal(__test__.promptMessage({ systemMessage: "m", hookSpecificOutput: { additionalContext: "no focus here" } }), "m")
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
  // An allowed run is silent and exits 0; the adapter must read that as allow, not failure.
  assert.deepEqual(await __test__.runGate(PATHS, "tool", bash, 10000), {})
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
  assert.deepEqual(await __test__.runGate(PATHS, "tool", { ...bash, cwd: plain }, 10000), {})
})

/** A stand-in plugin root whose launcher prints `body` (a shell fragment) for every gate call. */
function fakeRoot(body) {
  const root = mkdtempSync(join(tmpdir(), "mx-fakeroot-"))
  mkdirSync(join(root, "hooks"))
  writeFileSync(join(root, "hooks", "py.sh"), "cat >/dev/null\n" + body + "\n")
  writeFileSync(join(root, "hooks", "gate_run.py"), "")
  return root
}

async function setupWith(root, repo) {
  const made = fakeCtx(repo)
  made.ctx.options = { root }
  await plugin.setup(made.ctx)
  return made
}

const SHELL = (id) => ({ tool: "shell", input: { command: "ls" }, sessionID: "s", id })

test("a failed gate run is shown to the human, not swallowed", async () => {
  const { handlers } = await setupWith(fakeRoot("exit 1"), gatedRepo())
  await handlers.before[0](SHELL("c1")) // fails open, as on Claude Code
  const event = { ...SHELL("c1"), status: "completed", result: { content: "out" } }
  await handlers.after[0](event)
  assert.match(event.result.content, /^out\n\n/)
  assert.match(event.result.content, /gate error \(tool\).*not checked/)
  assert.match(event.result.content, /gate error \(post\)/)
  assert.doesNotMatch(event.result.content, /[*#`]/)
})

test("a failed tool call still receives the gate's notice", async () => {
  // There is no result to append to, so the notice must reach the session as a message instead of vanishing.
  const { handlers, calls } = await setupWith(fakeRoot("exit 1"), gatedRepo())
  await handlers.before[0](SHELL("c1"))
  await handlers.after[0]({ ...SHELL("c1"), status: "failed", error: { message: "boom" } })
  assert.deepEqual(calls.synthetic.map((message) => message.sessionID), ["s"])
  assert.match(calls.synthetic[0].text, /gate error \(tool\).*not checked/)
})

test("a timed-out gate resolves null", async () => {
  const root = fakeRoot("sleep 5")
  const reply = await __test__.runGate({ py: join(root, "hooks", "py.sh"), gate: "g" }, "tool", {}, 200)
  assert.equal(reply, null)
})

test("a tool reply's systemMessage reaches the tool result", async () => {
  const { handlers } = await setupWith(
    fakeRoot(`echo '{"systemMessage":"pinned input changed","hookSpecificOutput":{"additionalContext":"ctx line"}}'`), gatedRepo())
  await handlers.before[0](SHELL("c1"))
  const event = { ...SHELL("c1"), status: "completed", result: { content: "out" } }
  await handlers.after[0](event)
  assert.match(event.result.content, /pinned input changed\n\nctx line/)
  assert.equal(event.result.content.split("pinned input changed").length, 2, "shown once, not once per event")
})

test("on_error deny blocks a call the gate could not check", async () => {
  const repo = gatedRepo()
  writeFileSync(join(repo, ".mycelium-extra", "gate.json"), JSON.stringify({ on_error: "deny" }))
  const { handlers } = await setupWith(fakeRoot("exit 1"), repo)
  await assert.rejects(handlers.before[0](SHELL("c1")), /on_error to deny/)
  const other = await setupWith(fakeRoot("exit 1"), gatedRepo())
  await other.handlers.before[0](SHELL("c2")) // default on_error allow
})

test("a wrong root option warns visibly instead of going inert", async () => {
  const lines = []
  const original = console.error
  console.error = (...args) => lines.push(args.join(" "))
  let made
  try { made = await setupWith(join(tmpdir(), "mx-no-such-root"), gatedRepo()) } finally { console.error = original }
  assert.match(lines.join("\n"), /hooks not found/)
  assert.equal(made.handlers.before.length, 1, "the gate must stay wired so calls fail visibly")
  const event = { ...SHELL("c1"), status: "completed", result: { content: "out" } }
  await made.handlers.before[0](SHELL("c1"))
  await made.handlers.after[0](event)
  assert.match(event.result.content, /gate error \(tool\)/)
  const prompt = { text: "hello" }
  await made.handlers.prompt[0]({ prompt, sessionID: "s" })
  assert.match(made.calls.synthetic[0].text, /gate error \(prompt\)/)
})

test("a blocked prompt reaches the human through a synthetic message", async () => {
  const { handlers, calls } = await setupWith(
    fakeRoot(`echo '{"decision":"block","reason":"no pending plan abcd1234"}'`), gatedRepo())
  const prompt = { text: "card abcd1234" }
  await handlers.prompt[0]({ prompt, sessionID: "s9" })
  assert.deepEqual(calls.synthetic, [{ sessionID: "s9", text: "no pending plan abcd1234" }])
  assert.match(prompt.text, /handled the user's message/)
})
