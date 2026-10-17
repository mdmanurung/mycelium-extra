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
 * whose location is this plugin instance's.
 */
import { spawn } from "node:child_process"
import { existsSync, realpathSync } from "node:fs"
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
    let out = ""
    let done = false
    const finish = (value) => {
      if (done) return
      done = true
      clearTimeout(timer)
      try { resolve(value) } catch { resolve(null) }
    }
    const timer = setTimeout(() => {
      child.kill("SIGKILL")
      finish(null)
    }, timeout)
    child.stdout.on("data", (chunk) => {
      out += chunk
      if (out.length > MAX_OUTPUT) {
        child.kill("SIGKILL")
        finish(null)
      }
    })
    child.on("error", () => finish(null))
    child.on("close", () => {
      const text = out.trim()
      if (!text) return finish(null)
      try { finish(JSON.parse(text)) } catch { finish(null) }
    })
    child.stdin.on("error", () => {})
    child.stdin.end(JSON.stringify(payload))
  })
}

function hookOutput(reply) {
  return (reply && reply.hookSpecificOutput) || {}
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

export default {
  id: "mycelium-extra",
  async setup(ctx) {
    const derived = dirname(dirname(fileURLToPath(import.meta.url)))
    const root = (ctx.options && ctx.options.root) || derived
    const paths = { root, py: join(root, "hooks", "py.sh"), gate: join(root, "hooks", "gate_run.py") }
    if (!existsSync(paths.py) || !existsSync(paths.gate)) {
      console.error("mycelium-extra: hooks not found under " + root +
        "; set the plugin option root to the mycelium-extra checkout.")
      return
    }
    const place = (ctx.location && ctx.location.directory) || process.cwd()
    const notes = new Map() // call id -> a PreToolUse notice to show with the result

    function gated(cwd) {
      return findRoot(cwd || place) !== null
    }

    await ctx.tool.hook("execute.before", async (event) => {
      if (!TOOLS.has(event.tool)) return
      const input = event.input && typeof event.input === "object" ? event.input : {}
      const cwd = event.tool === "shell" && typeof input.workdir === "string" && input.workdir
        ? input.workdir : place
      if (!gated(cwd)) return
      const reply = await runGate(paths, "tool", toolEvent(event, cwd), TIMEOUTS.tool)
      const reason = denyReason(reply)
      if (reason) throw new Error(reason)
      const notice = hookOutput(reply).additionalContext
      if (typeof notice === "string" && notice) notes.set(event.id, notice)
    })

    await ctx.tool.hook("execute.after", async (event) => {
      if (!TOOLS.has(event.tool)) return
      const input = event.input && typeof event.input === "object" ? event.input : {}
      const cwd = event.tool === "shell" && typeof input.workdir === "string" && input.workdir
        ? input.workdir : place
      const notice = notes.get(event.id)
      notes.delete(event.id)
      if (!gated(cwd)) return
      const payload = toolEvent(event, cwd)
      payload.status = event.status
      if (event.status === "completed") payload.tool_response = event.result
      else payload.error = event.error && typeof event.error === "object"
        ? { message: String(event.error.message || ""), metadata: event.error.metadata } : String(event.error || "")
      const reply = await runGate(paths, "post", payload, TIMEOUTS.post)
      const extra = [notice, hookOutput(reply).additionalContext].filter(
        (text) => typeof text === "string" && text).join("\n\n")
      if (extra && event.status === "completed") {
        event.result = appendContent(event.result, extra)
      }
    })

    await ctx.session.hook("prompt", async (event) => {
      if (!gated(place)) return
      const payload = { prompt: event.prompt.text, cwd: place, session_id: event.sessionID }
      const reply = await runGate(paths, "prompt", payload, TIMEOUTS.prompt)
      if (!reply) return
      const message = reply.systemMessage || hookOutput(reply).additionalContext
      if (reply.decision === "block") {
        event.prompt.text = blockedPromptText(reply.reason || message || "handled by the approval gate.")
      } else if (typeof message === "string" && message) {
        event.prompt.text = event.prompt.text + "\n\n" + message
      }
    })

    const lastText = new Map() // session id -> the assistant text the Stop event will read
    const stopped = new Map()  // session id -> the text already run through stop, so idling twice is one stop
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
            if (mine === true) lastText.set(ended.sessionID, ended.text)
            continue
          }
          const sessionID = idleSession(event)
          if (!sessionID) continue
          if (mine === false) continue
          if (mine === null && !lastText.has(sessionID)) continue // unknown scope: only sessions first seen here
          const text = lastText.get(sessionID) || ""
          if (stopped.get(sessionID) === text) continue // idling twice over one turn is one stop
          stopped.set(sessionID, text)
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
      if (!reply) return
      const output = hookOutput(reply)
      const notice = reply.systemMessage || output.additionalContext
      if (reply.decision === "block") {
        // Claude's Stop hook blocks a turn and re-invokes the model with the reason; an idle
        // session is continued the same way.
        try {
          await ctx.session.prompt({ sessionID, text: reply.reason || notice,
            delivery: "steer" })
        } catch { /* the session may have been removed */ }
        return
      }
      if (typeof notice === "string" && notice && typeof ctx.session.synthetic === "function") {
        // Approval cards and explore notices must reach the user; synthetic messages stay in
        // the session without invoking the prompt hook.
        try {
          await ctx.session.synthetic({ sessionID, text: notice })
        } catch { /* the session may have been removed */ }
      }
    }

    return () => controller.abort()
  },
}

// Pure helpers, exercised by opencode/tests/gate.test.js under `node --test`.
export const __test__ = {
  appendContent, blockedPromptText, contentText, denyReason, eventLocation, findRoot, idleSession,
  runGate, samePlace, textEnded,
}
