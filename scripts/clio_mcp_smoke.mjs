/** Verify exports and the real Clio stdio client without live Zulip access. */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

const { values } = parseArgs({ options: {
  "clio-repo": { type: "string" },
  "server-command": { type: "string" },
  "integrate-command": { type: "string" },
  "expected-version": { type: "string" },
} });
for (const option of ["clio-repo", "server-command", "integrate-command", "expected-version"]) {
  assert(values[option], `Missing --${option}`);
}
const clioRoot = path.resolve(values["clio-repo"]);
const load = (relative) => import(pathToFileURL(path.join(clioRoot, "src", relative)).href);
const { loadMcpServerConfig } = await load("domains/gateway/mcp/config.ts");
const { validateLibraryPackage } = await load("domains/resources/library-validation.ts");
const { createMcpStdioClient } = await load("domains/gateway/mcp/client.ts");
const workspace = mkdtempSync(path.join(tmpdir(), "zulipchat-clio-"));
const credentials = path.join(workspace, "zuliprc");
const fakeEnv = {
  ZULIP_CONFIG_FILE: credentials, ZULIP_BOT_CONFIG_FILE: credentials,
  ZULIP_EMAIL: "test@example.com", ZULIP_API_KEY: "test-key",
  ZULIP_BOT_EMAIL: "test@example.com", ZULIP_BOT_API_KEY: "test-key",
  ZULIP_SITE: "http://127.0.0.1:9", ANTHROPIC_API_KEY: "",
  ZULIPCHAT_DB_PATH: path.join(workspace, "smoke.duckdb"),
};
let client;
try {
  writeFileSync(credentials, "[api]\nemail=test@example.com\nkey=test-key\nsite=http://127.0.0.1:9\n");
  for (const mode of ["standalone", "plugin"]) {
    const output = mode === "standalone" ? workspace : path.join(workspace, "plugin");
    const exported = spawnSync(path.resolve(values["integrate-command"]), [
      "export", "--client", "clio-coder", "--mode", mode,
      "--output-dir", output, "--zulip-config-file", credentials, "--extended-tools",
    ], { cwd: workspace, env: { ...process.env, ...fakeEnv }, encoding: "utf8" });
    assert.equal(exported.status, 0, exported.stderr);
  }
  const config = loadMcpServerConfig({ cwd: workspace, configDir: path.join(workspace, "empty-user") });
  assert.deepEqual(config.diagnostics, []);
  assert.equal(config.servers.length, 1);
  assert.equal(config.servers[0].timeoutMs, 900000);
  const validated = validateLibraryPackage(path.join(workspace, "plugin"), { cwd: workspace });
  assert.equal(validated.valid, true, JSON.stringify(validated.diagnostics));
  console.log("ok: actual Clio config parser and portable plugin validator");

  client = createMcpStdioClient({
    id: "zulipchat", command: path.resolve(values["server-command"]),
    args: config.servers[0].args.slice(1), cwd: workspace, env: fakeEnv,
  }, { workspaceRoot: workspace, initializeTimeoutMs: 60000, requestTimeoutMs: 20000 });
  const discovered = await client.initialize();
  assert.equal(discovered.protocolVersion, "2025-06-18");
  assert.equal((await client.listTools()).tools.length, 60);
  const info = await client.callTool("server_info", {});
  assert.equal(info.isError, false);
  assert.equal(info.structuredContent.version, values["expected-version"]);
  // Explicit owner and stream avoid any Zulip lookup; these calls use local state.
  const registered = await client.callTool("register_agent", {
    agent_name: "clio-smoke", agent_type: "clio-coder",
    owner_email: "test@example.com", stream_name: "Agents-Channel",
  });
  assert.equal(registered.structuredContent.status, "success");
  const bound = await client.callTool("ensure_agent_session", {
    agent_id: registered.structuredContent.agent_id,
    external_session_id: "clio-smoke", project_dir: workspace,
  });
  assert.equal(bound.structuredContent.status, "success");
  console.log(`ok: Clio MCP 2025-06-18, 60 tools, server_info v${values["expected-version"]}, profile/session binding`);
} finally {
  if (client) await client.close();
  rmSync(workspace, { recursive: true, force: true });
}
