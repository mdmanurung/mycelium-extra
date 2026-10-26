/**
 * Mycelium Extra approval-gate adapter for OpenCode V2.
 *
 * Thin host glue: every decision stays in the shared Python gate. This plugin maps OpenCode's
 * tool and prompt events onto `hooks/gate_run.py --host opencode` and the reply back onto
 * OpenCode behavior (a thrown error is a deny; text is appended to the tool result; a blocked
 * prompt is rewritten). It imports nothing beyond Node/Bun builtins, so the OpenCode plugin
 * package is not needed at runtime.
 *
 * Load it from opencode.json(c) as a plugin directory:
 *   { "plugins": ["/absolute/path/to/mycelium-extra/opencode"] }
 * For a checkout in a nonstandard place, pass { "package": "...opencode", "options": { "root": "/path/to/mycelium-extra" } }.
 *
 * The adapter is inert unless the repository has `.mycelium-extra/gate.json`; it never runs
 * the gate for repositories without one, so an ungated checkout pays only a directory walk.
 * The server's event stream is service-wide on 2.0.32, so the stop handler keeps only events
 * whose location is this plugin instance's, and its turn-end boundary is
 * session.execution.succeeded (2.0.32 emits no session.idle).
 */
import { spawn } from "node:child_process"
import { existsSync, readdirSync, readFileSync, realpathSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const TOOLS = new Set(["shell", "edit", "write", "patch"])
const TIMEOUTS = { prompt: 10000, tool: 10000, post: 20000, stop: 30000 }
const MAX_OUTPUT = 1 << 20 // the gate's replies are small; cap a runaway stream

function findRoot(start) {
  let dir = start || "/"
  for (;;) {
    if (existsSync(join(dir, ".mycelium-extra", "gate.json"))) return dir
    const parent = dirname(dir)
    if (parent === dir) return null
    dir = parent
  }
}

function runGate(paths, action, payload, timeout) {
  return new Promise((resolve) => {
    let child
    try {
      child = spawn("sh", [paths.py, "--hook", paths.gate, "--host", "opencode", action], {
        stdio: ["pipe", "pipe", "ignore"],
      })
    } catch {
      resolve(null)
      return
    }
    const chunks = []
    let size = 0
    let done = false
    const finish = (value) => {
      if (done) return
      done = true
      clearTimeout(timer)
      resolve(value)
    }
    const timer = setTimeout(() => {
      child.kill("SIGKILL")
      finish(null)
    }, timeout)
    child.stdout.on("data", (chunk) => {
      chunks.push(chunk)
      size += chunk.length
      if (size > MAX_OUTPUT) {
        child.kill("SIGKILL")
        finish(null)
      }
    })
    child.on("error", () => finish(null))
    child.on("close", (code) => {
      // concat before decoding: a multi-byte card glyph can straddle chunks
      const text = Buffer.concat(chunks).toString("utf8").trim()
      if (!text) {
        // hooks/gate.py's emit() prints nothing when the gate has no objection, and the
        // Claude Code protocol reads that silence as allow. A non-zero exit or a signal
        // still means the gate did not run.
        return finish(code === 0 ? {} : null)
      }
      try { finish(JSON.parse(text)) } catch { finish(null) }
    })
    child.stdin.on("error", () => {})
    child.stdin.end(JSON.stringify(payload))
  })
}

function hookOutput(reply) {
  return (reply && reply.hookSpecificOutput) || {}
}

// What OpenCode appends to a prompt: the gate's user-facing message, else its agent context. When the reply
// carries both (a hint plus an open focus), the focus line travels in the context only, so it is added here.
function promptMessage(reply) {
  const context = hookOutput(reply).additionalContext
  if (!reply.systemMessage) return context
  const focus = typeof context === "string" ? context.split("\n").find((line) => line.startsWith("mycelium-extra focus:")) : null
  return focus && !String(reply.systemMessage).includes(focus) ? reply.systemMessage + "\n" + focus : reply.systemMessage
}

// gate.json's on_error, read the way hooks/gate_run.py reads it: only an explicit "deny" opts in.
function onErrorDeny(cwd) {
  try {
    const root = findRoot(cwd)
    return JSON.parse(readFileSync(join(root, ".mycelium-extra", "gate.json"), "utf8")).on_error === "deny"
  } catch {
    return false
  }
}

function gateFailure(action) {
  return "mycelium-extra gate error (" + action + "): the gate did not run (timeout, spawn failure, or an unreadable reply)" +
    (action === "tool" ? "; this call was not checked and pinned inputs were not re-checked." :
      action === "post" ? "; no run receipt was recorded for this call." : ".")
}

// The user-facing text of a tool-event reply: its systemMessage and agent context, without repeats.
function toolNotice(reply) {
  const context = hookOutput(reply).additionalContext
  return [reply && reply.systemMessage, context].filter(
    (text, i, all) => typeof text === "string" && text && all.indexOf(text) === i).join("\n\n")
}

function denyReason(reply) {
  const output = hookOutput(reply)
  if (output.permissionDecision !== "deny") return null
  return output.permissionDecisionReason || "mycelium-extra: blocked."
}

function contentText(content) {
  if (typeof content === "string") return content
  if (Array.isArray(content)) {
    return content.filter((part) => part && part.type === "text" && typeof part.text === "string")
      .map((part) => part.text).join("\n")
  }
  return ""
}

function appendContent(result, text) {
  const base = result && typeof result === "object" ? result : {}
  const content = base.content
  if (Array.isArray(content)) return { ...base, content: [...content, { type: "text", text }] }
  if (typeof content === "string") return { ...base, content: content ? content + "\n\n" + text : text }
  if (content === undefined || content === null) return { ...base, content: text }
  return base // an unknown content shape is left alone rather than replaced
}

function blockedPromptText(reason) {
  return [
    "mycelium-extra handled the user's message itself; it was not an instruction to you.",
    "For the user: " + reason,
    "Take no action beyond passing that on. Do not start, approve, or run anything.",
  ].join("\n\n")
}

function toolEvent(event, cwd) {
  return {
    tool_name: event.tool,
    tool_input: event.input,
    cwd,
    session_id: event.sessionID,
    tool_use_id: event.id,
  }
}

/** The cwd the gate should see: a command's own working directory when it sits under a gated
 *  checkout, else the session location when that does, else null (no gate applies). A shell
 *  `workdir` outside every gate must not silently switch the gate off. */
function gateCwd(cwd, place) {
  if (cwd && findRoot(cwd)) return cwd
  if (place && findRoot(place)) return place
  return null
}

/** One command per skill folder, mirroring `/mycelium-extra:<skill>` in Claude Code. The
 *  description is the skill's own first sentence, so the command list reads like the skills. */
function skillCommands(root) {
  const dir = join(root, "skills")
  let entries = []
  try {
    entries = readdirSync(dir, { withFileTypes: true })
  } catch {
    return []
  }
  return entries
    .filter((entry) => entry.isDirectory() && existsSync(join(dir, entry.name, "SKILL.md")))
    .map((entry) => {
      let description = "Run the mycelium-extra " + entry.name + " skill"
      try {
        const match = /^description:[ \t]*(.+)$/m.exec(readFileSync(join(dir, entry.name, "SKILL.md"), "utf8"))
        if (match) {
          const first = match[1].trim().replace(/^["']|["']$/g, "").split(". ")[0]
          if (first) description = first.slice(0, 150)
        }
      } catch {
        // the folder stays listed with the fallback description
      }
      return { id: entry.name, description }
    })
    .sort((a, b) => a.id.localeCompare(b.id))
}

function commandText(root, id, arguments_) {
  return "Load the mycelium-extra skill `" + id + "` with the skill tool (its folder is " +
    join(root, "skills", id) + "), then carry it out for this request:\n\n" + (arguments_ || "")
}

/** V2 server events carry their payload under `data`; older shapes were flat. */
function eventData(event) {
  return event && event.data && typeof event.data === "object" ? event.data : {}
}

function eventLocation(event) {
  const location = event && event.location
  return location && typeof location.directory === "string" ? location.directory : null
}

function samePlace(a, b) {
  if (a === b) return true
  try {
    return realpathSync(a) === realpathSync(b)
  } catch {
    return false
  }
}

function textEnded(event) {
  if (!event || event.type !== "session.text.ended") return null
  const data = eventData(event)
  const sessionID = data.sessionID || event.sessionID
  const text = typeof data.text === "string" ? data.text : event.text
  return sessionID && typeof text === "string" ? { sessionID, text } : null
}

function idleSession(event) {
  if (!event || event.type !== "session.idle") return null
  const data = eventData(event)
  return data.sessionID || event.sessionID || null
}

/** The turn-end boundary. 2.0.32 delivers session.execution.succeeded and no session.idle;
 *  the idle shape stays supported in case a build emits it. */
function executionEnded(event) {
  if (!event || typeof event.type !== "string") return null
  if (!/^session\.execution\.(succeeded|failed|interrupted)$/.test(event.type)) return null
  const data = eventData(event)
  return data.sessionID || event.sessionID || null
}

export default {
  id: "mycelium-extra",
  async setup(ctx) {
    const derived = dirname(dirname(fileURLToPath(import.meta.url)))
    const root = (ctx.options && ctx.options.root) || derived
    const paths = { root, py: join(root, "hooks", "py.sh"), gate: join(root, "hooks", "gate_run.py") }
    if (!existsSync(paths.py) || !existsSync(paths.gate)) {
      console.error("mycelium-extra: hooks not found under " + root +
        "; set the plugin option root to the mycelium-extra checkout.")
      // Stay loaded: every gate call then fails visibly (a note, or a deny under on_error) instead of the adapter going inert.
    }
    const place = (ctx.location && ctx.location.directory) || process.cwd()
    const notes = new Map() // call id -> a PreToolUse notice to show with the result

    function gated(cwd) {
      return findRoot(cwd || place) !== null
    }

    // Command entry points: `/mycelium-extra:<skill>` here, as `/mycelium-extra:<skill>` in
    // Claude Code and `$mycelium-extra:<skill>` in Codex. Each submits the skill's name and
    // folder, so the command works whether or not the checkout is also a `skills` source.
    const skills = skillCommands(root)
    if (skills.length && ctx.command && typeof ctx.command.transform === "function") {
      await ctx.command.transform((editor) => {
        for (const skill of skills) {
          editor.add({
            name: "mycelium-extra:" + skill.id,
            description: skill.description,
            execute: async ({ sessionID, prompt, delivery }) => {
              await ctx.session.prompt(
                { ...prompt, sessionID, text: commandText(root, skill.id, prompt && prompt.text), delivery })
            },
          })
        }
      })
    }

    await ctx.tool.hook("execute.before", async (event) => {
      if (!TOOLS.has(event.tool)) return
      const input = event.input && typeof event.input === "object" ? event.input : {}
      const requested = event.tool === "shell" && typeof input.workdir === "string" && input.workdir
        ? input.workdir : place
      const cwd = gateCwd(requested, place)
      if (!cwd) return
      const reply = await runGate(paths, "tool", toolEvent(event, cwd), TIMEOUTS.tool)
      let notice
      if (!reply) {
        notice = gateFailure("tool")
        if (onErrorDeny(cwd)) {
          throw new Error(notice.replace(/; this call was not checked.*$/, "") +
            "; blocked because gate.json sets on_error to deny. Do not work around this block; the user can fix the gate or set on_error to allow.")
        }
      } else {
        const reason = denyReason(reply)
        if (reason) throw new Error(reason)
        notice = toolNotice(reply)
      }
      if (notice) {
        while (notes.size > 64) notes.delete(notes.keys().next().value) // drop the oldest: a before without an after (rejected permission) must not leak
        notes.set(event.id, notice)
      }
    })

    await ctx.tool.hook("execute.after", async (event) => {
      if (!TOOLS.has(event.tool)) return
      const input = event.input && typeof event.input === "object" ? event.input : {}
      const requested = event.tool === "shell" && typeof input.workdir === "string" && input.workdir
        ? input.workdir : place
      const notice = notes.get(event.id)
      notes.delete(event.id)
      const cwd = gateCwd(requested, place)
      if (!cwd) return
      const payload = toolEvent(event, cwd)
      payload.status = event.status
      if (event.status === "completed") payload.tool_response = event.result
      else payload.error = event.error && typeof event.error === "object"
        ? { message: String(event.error.message || ""), metadata: event.error.metadata } : String(event.error || "")
      const reply = await runGate(paths, "post", payload, TIMEOUTS.post)
      const extra = [notice, reply ? toolNotice(reply) : gateFailure("post")].filter(
        (text, i, all) => typeof text === "string" && text && all.indexOf(text) === i).join("\n\n")
      // A failed call has no result to append to; the notice must still reach the session, not vanish.
      if (extra && event.status === "completed") event.result = appendContent(event.result, extra)
      else if (extra && typeof event.sessionID === "string" && event.sessionID) await tell(event.sessionID, extra)
    })

    // A message for the human: synthetic messages stay in the session without invoking the prompt hook.
    async function tell(sessionID, text) {
      if (typeof ctx.session.synthetic !== "function") return
      try {
        await ctx.session.synthetic({ sessionID, text })
      } catch { /* the session may have been removed */ }
    }

    await ctx.session.hook("prompt", async (event) => {
      if (!gated(place)) return
      const payload = { prompt: event.prompt.text, cwd: place, session_id: event.sessionID }
      const reply = await runGate(paths, "prompt", payload, TIMEOUTS.prompt)
      if (!reply) return tell(event.sessionID, gateFailure("prompt"))
      const message = promptMessage(reply)
      if (reply.decision === "block") {
        // The rewrite below reaches only the agent; the human gets the gate's own words directly.
        await tell(event.sessionID, reply.reason || message || "handled by the approval gate.")
        event.prompt.text = blockedPromptText(reply.reason || message || "handled by the approval gate.")
      } else if (typeof message === "string" && message) {
        event.prompt.text = event.prompt.text + "\n\n" + message
      }
    })

    const lastText = new Map() // session id -> the assistant text the Stop event will read
    const stopped = new Map()  // session id -> the text already run through stop, so a repeated boundary is one stop
    const MAX_SESSIONS = 50    // the server is long-lived; plan texts are kilobytes
    function remember(map, key, value) {
      map.delete(key)
      map.set(key, value)
      while (map.size > MAX_SESSIONS) map.delete(map.keys().next().value)
    }
    const controller = new AbortController()
    void (async () => {
      try {
        for await (const event of ctx.event.subscribe({ signal: controller.signal })) {
          // The 2.0.32 server event stream is service-wide: every loaded plugin receives
          // every location's session events (checked 2026-10-17). Only this location's
          // sessions belong to this gate instance.
          const where = eventLocation(event)
          const mine = where === null ? null : samePlace(where, place)
          const ended = textEnded(event)
          if (ended) {
            if (mine === true) remember(lastText, ended.sessionID, ended.text)
            continue
          }
          const sessionID = executionEnded(event) || idleSession(event)
          if (!sessionID) continue
          if (mine === false) continue
          if (mine === null && !lastText.has(sessionID)) continue // unknown scope: only sessions first seen here
          const text = lastText.get(sessionID) || ""
          if (stopped.get(sessionID) === text) continue // a repeated boundary over one turn is one stop
          remember(stopped, sessionID, text)
          await stop(sessionID, text)
        }
      } catch {
        // the stream aborted at unload
      }
    })()

    async function stop(sessionID, text) {
      if (!gated(place)) return
      const reply = await runGate(paths, "stop",
        { last_assistant_message: text, cwd: place, session_id: sessionID }, TIMEOUTS.stop)
      if (!reply) return tell(sessionID, gateFailure("stop"))
      const output = hookOutput(reply)
      const notice = reply.systemMessage || output.additionalContext
      if (reply.decision === "block") {
        // Claude's Stop hook blocks a turn and re-invokes the model with the reason; a
        // finished turn is continued the same way.
        try {
          await ctx.session.prompt({ sessionID, text: reply.reason || notice,
            delivery: "steer" })
        } catch { /* the session may have been removed */ }
        return
      }
      // Approval cards and explore notices must reach the user.
      if (typeof notice === "string" && notice) await tell(sessionID, notice)
    }

    return () => controller.abort()
  },
}

// Pure helpers, exercised by opencode/tests/gate.test.js under `node --test`.
export const __test__ = {
  appendContent, blockedPromptText, commandText, contentText, denyReason, eventLocation, gateFailure, onErrorDeny, toolNotice,
  executionEnded, findRoot, gateCwd, idleSession, promptMessage, runGate, samePlace, skillCommands, textEnded,
}
