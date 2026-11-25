/**
 * Drive a built PanCode CLI against this package with a mock Zulip.
 *
 *   node scripts/pancode_mcp_smoke.mjs --pancode <bin> --workdir <dir> [--bridge]
 *
 * Standalone export into a scratch project, launch trust, surface approval by
 * digest, then server_info and get_streams through `uvx zulipchat-mcp@<pin>`.
 * --bridge also runs the agent bridge with `pancode acp` and checks that one
 * DM from the owner gets the bot's reply. That leg needs a live model: the
 * scratch PanCode home's only target is openai-codex, its credential copied
 * from --credentials without printing it. Nothing here imports PanCode.
 */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import http from "node:http";
import { homedir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const { values } = parseArgs({
  options: {
    pancode: { type: "string" },
    workdir: { type: "string" },
    bridge: { type: "boolean", default: false },
    credentials: { type: "string", default: path.join(homedir(), ".config/pancode/credentials.yaml") },
    "reply-timeout": { type: "string", default: "300" },
  },
});
assert(values.pancode, "Missing --pancode <bin>");
assert(values.workdir, "Missing --workdir <dir>");
const pancode = path.resolve(values.pancode);
const workdir = path.resolve(values.workdir);
const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const project = path.join(workdir, "project");
const home = path.join(workdir, "pancode-home");
for (const dir of [project, home]) mkdirSync(dir, { recursive: true });
const log = (line) => console.log(line);

// Child processes see only scratch homes: no inherited PanCode directories and
// no Zulip credentials from the caller's environment.
const baseEnv = Object.fromEntries(
  Object.entries(process.env).filter(([key]) => !key.startsWith("PANCODE_") && !key.startsWith("ZULIP")),
);
const pancodeEnv = { ...baseEnv, PANCODE_HOME: home, PANCODE_REQUIRE_HOME_PREFIX: "1" };

// A minimal Zulip: the owner (7), the owner's bot (9), one channel, an event
// queue the smoke feeds, and a log of every message posted.
const OWNER = { user_id: 7, email: "owner@example.com", full_name: "Owner", is_bot: false };
const BOT = { user_id: 9, email: "agent-bot@example.com", full_name: "Agent", is_bot: true, bot_type: 1, bot_owner_id: 7 };
const CHANNEL = { stream_id: 1, name: "smoke-channel", description: "Mock channel", invite_only: false, is_web_public: false };
const people = [OWNER, BOT];
const posted = [];
const pending = [];
const registered = [];
let eventId = 0;
let messageId = 3000;
const ok = (res, body) => {
  res.writeHead(200, { "content-type": "application/json" });
  res.end(JSON.stringify({ result: "success", msg: "", ...body }));
};
const zulip = http.createServer((req, res) => {
  let raw = "";
  req.on("data", (chunk) => { raw += chunk; });
  req.on("end", () => {
    const url = new URL(req.url, "http://zulip");
    const form = Object.fromEntries(new URLSearchParams(raw));
    const login = Buffer.from((req.headers.authorization ?? " Og==").split(" ")[1], "base64").toString().split(":")[0];
    const route = `${req.method} ${url.pathname.replace("/api/v1/", "")}`;
    const user = /^GET users\/(\d+)$/.exec(route);
    if (route === "GET server_settings") return ok(res, { zulip_version: "11.0", zulip_feature_level: 400 });
    if (route === "GET users/me") return ok(res, login === BOT.email ? BOT : OWNER);
    if (user) return ok(res, { user: people.find((person) => person.user_id === Number(user[1])) ?? {} });
    if (route === "GET users") return ok(res, { members: people });
    if (route === "GET streams") return ok(res, { streams: [CHANNEL] });
    if (route === "GET users/me/subscriptions") return ok(res, { subscriptions: [CHANNEL] });
    if (route === "POST register") {
      registered.push(login);
      return ok(res, { queue_id: `q${registered.length}`, last_event_id: -1 });
    }
    if (route === "GET events") {
      const send = () => ok(res, { events: pending.splice(0) });
      return pending.length ? send() : setTimeout(send, 300);
    }
    if (route === "GET messages") return ok(res, { messages: [], found_newest: true, found_oldest: true });
    if (route === "POST messages") {
      messageId += 1;
      posted.push({ id: messageId, login, type: form.type, to: JSON.parse(form.to), content: form.content });
      return ok(res, { id: messageId });
    }
    return ok(res, {});
  });
});
await new Promise((resolve) => zulip.listen(0, "127.0.0.1", resolve));
const site = `http://127.0.0.1:${zulip.address().port}`;
const ownerRc = path.join(workdir, "owner.zuliprc");
const botRc = path.join(workdir, "bot.zuliprc");
writeFileSync(ownerRc, `[api]\nemail=${OWNER.email}\nkey=placeholder-key\nsite=${site}\n`, { mode: 0o600 });
writeFileSync(botRc, `[api]\nemail=${BOT.email}\nkey=placeholder-key\nsite=${site}\n`, { mode: 0o600 });

// Asynchronous, so the mock Zulip keeps answering while a child calls it.
function run(command, args, options = {}) {
  log(`$ ${[path.basename(command), ...args].join(" ")}`);
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { ...options, stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    const timer = setTimeout(() => child.kill("SIGTERM"), 600_000);
    child.on("error", reject);
    child.on("close", (status) => { clearTimeout(timer); resolve({ status, stdout, stderr }); });
  });
}

async function pan(args, expectCode = 0) {
  const result = await run(pancode, args, { cwd: project, env: pancodeEnv });
  assert.equal(result.status, expectCode, `${args.join(" ")} exited ${result.status}\n${result.stdout}\n${result.stderr}`);
  return JSON.parse(result.stdout);
}

async function mcpSmoke() {
  const exported = await run("uv", [
    "run", "--project", repo, "zulipchat-mcp-integrate", "export", "--client", "pancode",
    "--output-dir", project, "--zulip-config-file", ownerRc,
  ], { cwd: repo, env: baseEnv });
  assert.equal(exported.status, 0, exported.stderr);
  const config = readFileSync(path.join(project, ".pancode/mcp.yaml"), "utf8");
  const pin = /zulipchat-mcp@([0-9][\w.]*)/.exec(config)?.[1];
  assert(pin, "export pins no zulipchat-mcp version");
  log(`exported .pancode/mcp.yaml: uvx zulipchat-mcp@${pin}`);

  const trusted = await pan(["mcp", "trust", "zulipchat", "--json"]);
  assert.equal(trusted.ok, true);
  const classes = trusted.toolActionClasses;
  log(`launch trust ${trusted.record.digest}: ${Object.keys(classes).length} tool classes`);
  for (const [tool, actionClass] of Object.entries(classes)) log(`  ${tool} ${actionClass}`);
  assert.equal(classes.edit_message, "destructive");
  assert.equal(classes.get_streams, "read");

  const listed = await pan(["mcp", "test", "zulipchat", "--json"]);
  assert.equal(listed.server.trust.status, "trusted");
  const digest = listed.surface?.digest;
  assert.match(digest ?? "", /^[a-f0-9]{64}$/, JSON.stringify(listed.surface));
  assert.equal(listed.tools.length, Object.keys(classes).length);
  log(`MCP ${listed.protocolVersion} ${listed.serverInfo?.name} ${listed.serverInfo?.version}: ${listed.tools.length} tools, surface ${listed.surface.status} ${digest}`);

  const approved = await pan(["mcp", "trust", "zulipchat", "--surface", "--hash", digest, "--json"]);
  assert.equal(approved.recorded, true, JSON.stringify(approved));
  log(`surface recorded: ${approved.surface.status} ${approved.surface.approvedDigest}`);

  const called = await pan(["mcp", "test", "zulipchat", "--call", "server_info", "--call", "get_streams", "--json"]);
  assert.equal(called.ok, true, JSON.stringify(called.calls));
  const [info, streams] = called.calls.map((call) => call.structuredContent ?? JSON.parse(call.text));
  assert.equal(info.version, pin);
  assert.equal(info.available_identities.user.email, OWNER.email);
  assert.equal(info.available_identities.user.site, site);
  assert.deepEqual(streams.streams.map((stream) => stream.name), [CHANNEL.name]);
  log(`server_info: ${info.server_name} ${info.version} as ${info.available_identities.user.email} at ${site}`);
  log(`get_streams: ${streams.streams.map((stream) => `#${stream.name}`).join(", ")}`);
  log("ok: PanCode MCP smoke");
}

/** The openai-codex entry of a PanCode credentials file, copied and never printed. */
function codexCredential(source) {
  const lines = readFileSync(source, "utf8").split("\n");
  const start = lines.findIndex((line) => /^ {2}openai-codex:\s*$/.test(line));
  assert(start >= 0, `${source} holds no openai-codex credential`);
  let end = start + 1;
  while (end < lines.length && /^ {4}\S/.test(lines[end])) end += 1;
  return ["version: 2", "entries:", ...lines.slice(start, end), ""].join("\n");
}

async function bridgeSmoke() {
  const config = path.join(home, "config");
  mkdirSync(config, { recursive: true });
  writeFileSync(path.join(config, "settings.yaml"), [
    "version: 2",
    "targets:",
    "  - id: openai-codex",
    "    runtime: openai-codex",
    "    defaultModel: gpt-6-luna",
    "    auth:",
    "      oauthProfile: openai-codex",
    "chat:",
    "  target: openai-codex",
    "  model: gpt-6-luna",
    "fleet:",
    "  default:",
    "    target: openai-codex",
    "    model: gpt-6-luna",
    "",
  ].join("\n"));
  const credentials = path.join(config, "credentials.yaml");
  writeFileSync(credentials, codexCredential(values.credentials), { mode: 0o600 });
  chmodSync(credentials, 0o600);

  const xdgConfig = path.join(workdir, "xdg-config");
  const xdgState = path.join(workdir, "xdg-state");
  const agents = path.join(xdgConfig, "zulipchat-mcp/agents");
  mkdirSync(agents, { recursive: true });
  const toml = (value) => JSON.stringify(value);
  writeFileSync(path.join(agents, "pancode.toml"), [
    `zuliprc = ${toml(botRc)}`,
    `command = [${toml(pancode)}, "acp"]`,
    `cwd = ${toml(project)}`,
    `zulip_tools = "ask"`,
    `listen = "dm"`,
    `env = { PANCODE_HOME = ${toml(home)}, PANCODE_REQUIRE_HOME_PREFIX = "1" }`,
    "",
  ].join("\n"));

  const env = { ...baseEnv, XDG_CONFIG_HOME: xdgConfig, XDG_STATE_HOME: xdgState };
  log("$ uv run zulipchat-mcp-agents run --agent pancode");
  const bridge = spawn("uv", ["run", "--project", repo, "zulipchat-mcp-agents", "run", "--agent", "pancode"], {
    cwd: repo, env, stdio: ["ignore", "pipe", "pipe"],
  });
  let output = "";
  bridge.stdout.on("data", (chunk) => { output += chunk; });
  bridge.stderr.on("data", (chunk) => { output += chunk; });
  const deadline = Date.now() + Number(values["reply-timeout"]) * 1000;
  const waitFor = async (what, test) => {
    while (!test()) {
      assert(bridge.exitCode === null, `bridge exited ${bridge.exitCode} waiting for ${what}\n${output}`);
      assert(Date.now() < deadline, `timed out waiting for ${what}\n${output}`);
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  };
  try {
    await waitFor("the bot's event queue", () => registered.includes(BOT.email));
    const prompt = "Reply with the single word ready.";
    messageId += 1;
    const dm = messageId;
    pending.push({
      id: (eventId += 1), type: "message", flags: [],
      message: {
        id: dm, type: "private", sender_id: OWNER.user_id, sender_email: OWNER.email,
        sender_full_name: OWNER.full_name, client: "website", subject: "", content: prompt,
        timestamp: Math.floor(Date.now() / 1000),
        display_recipient: [OWNER, BOT].map(({ user_id, email, full_name }) => ({ id: user_id, email, full_name })),
      },
    });
    log(`owner DM ${dm} to the bot: ${prompt}`);
    const answer = () => posted.find((message) => message.login === BOT.email && !message.content.startsWith("⏳"));
    await waitFor("the bot's reply", answer);
    const reply = answer();
    assert.deepEqual(reply.to, [OWNER.user_id], "the reply is not in the owner's DM");
    assert(["direct", "private"].includes(reply.type), `the reply is a ${reply.type} message`);
    assert(reply.content.trim().length > 0, "the reply is empty");
    assert(!/^The agent (could not start|failed)/.test(reply.content), reply.content);
    log(`bot reply ${reply.id} in the owner's DM: ${reply.content}`);

    const { DatabaseSync } = await import("node:sqlite");
    const db = new DatabaseSync(path.join(xdgState, "zulipchat-mcp/agents/pancode.sqlite3"), { readOnly: true });
    const row = db.prepare("SELECT key, session_id FROM conversations").get();
    db.close();
    assert(row?.session_id, "the bridge recorded no PanCode session");
    log(`bridge conversation ${row.key}: PanCode session ${row.session_id}`);
    log("ok: PanCode bridged message");
  } finally {
    bridge.kill("SIGTERM");
    await new Promise((resolve) => (bridge.exitCode === null ? bridge.once("exit", resolve) : resolve()));
  }
}

try {
  await mcpSmoke();
  if (values.bridge) {
    assert(existsSync(values.credentials), `no PanCode credentials at ${values.credentials}`);
    await bridgeSmoke();
  }
} finally {
  zulip.close();
}
