import { spawn } from "child_process";

console.log("Starting MCP Server...");
const serverProcess = spawn("node", ["dist/index.js"], {
  cwd: "/root/.openclaw/workspace/projects/nouva-mcp-server",
});

let buffer = "";

serverProcess.stdout.on("data", (data) => {
  buffer += data.toString();
  console.log("\n--- RECEIVED FROM SERVER ---");
  console.log(data.toString().trim());
  console.log("----------------------------\n");
});

serverProcess.stderr.on("data", (data) => {
  console.error("SERVER STDERR:", data.toString().trim());
});

function sendRequest(method, params, id) {
  const req = {
    jsonrpc: "2.0",
    id,
    method,
    params,
  };
  const payload = JSON.stringify(req) + "\n";
  console.log(`SENDING ${method}:`, JSON.stringify(req));
  serverProcess.stdin.write(payload);
}

// 1. Send initialize request
setTimeout(() => {
  sendRequest("initialize", {
    protocolVersion: "2024-11-05",
    capabilities: {},
    clientInfo: { name: "test-client", version: "1.0.0" }
  }, 1);
}, 1000);

// 2. Send tools/list request
setTimeout(() => {
  sendRequest("tools/list", {}, 2);
}, 2000);

// 3. Send tools/call request for system_status
setTimeout(() => {
  sendRequest("tools/call", { name: "system_status", arguments: {} }, 3);
}, 3000);

// 4. Send tools/call request for run_safe_command (safe command)
// 5. Send tools/call request for run_safe_command (blocked command)
// 6. Send resources/list request
// 7. Send resources/read request for contributing-gading-dev guidelines
// 8. Send tools/list request to verify review and publish tools
setTimeout(() => {
  sendRequest("tools/list", {}, 4);
}, 4000);

// 9. Send resources/list request
setTimeout(() => {
  sendRequest("resources/list", {}, 5);
}, 5000);

// 10. Send resources/read request for morning-report guidelines
setTimeout(() => {
  sendRequest("resources/read", { uri: "metadata://skills/morning-report/guidelines" }, 6);
}, 6000);

// Exit
setTimeout(() => {
  console.log("Shutting down test...");
  serverProcess.kill();
  process.exit(0);
}, 8000);
