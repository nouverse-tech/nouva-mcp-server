import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

// Initialize the MCP Server
const server = new Server(
  {
    name: "nouva-mcp-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Register available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "system_status",
        description: "Mendapatkan status performa sistem lokal (CPU, RAM, Disk space)",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "run_safe_command",
        description: "Menjalankan command shell terbatas di dalam workspace sandbox",
        inputSchema: {
          type: "object",
          properties: {
            command: {
              type: "string",
              description: "Command shell yang ingin dijalankan (misal: 'git status', 'ls -la')",
            },
          },
          required: ["command"],
        },
      },
    ],
  };
});

// Handle tool execution requests
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    if (name === "system_status") {
      const [uptimeRes, memRes, diskRes] = await Promise.all([
        execAsync("uptime"),
        execAsync("free -h"),
        execAsync("df -h /"),
      ]);

      const report = [
        "=== UPTIME & LOAD ===",
        uptimeRes.stdout.trim(),
        "",
        "=== MEMORY USAGE ===",
        memRes.stdout.trim(),
        "",
        "=== DISK SPACE (ROOT) ===",
        diskRes.stdout.trim(),
      ].join("\n");

      return {
        content: [
          {
            type: "text",
            text: report,
          },
        ],
      };
    }

    if (name === "run_safe_command") {
      const command = args?.command as string;
      
      // Basic security check: prevent dangerous commands
      const blockedKeywords = [";", "&&", "||", "|", ">", "<", "&", "rm ", "sudo", "elevated", "chmod", "chown", "mv "];
      const hasBlocked = blockedKeywords.some(keyword => command.includes(keyword));
      
      if (hasBlocked) {
        return {
          content: [
            {
              type: "text",
              text: `Error: Command mengandung karakter/keyword terlarang (${blockedKeywords.filter(k => command.includes(k)).join(", ")}). Hanya command sederhana yang diperbolehkan.`,
            },
          ],
          isError: true,
        };
      }

      // Execute command in workspace root
      const workspaceRoot = "/root/.openclaw/workspace";
      const { stdout, stderr } = await execAsync(command, { cwd: workspaceRoot });

      return {
        content: [
          {
            type: "text",
            text: [
              `Command: ${command}`,
              `Directory: ${workspaceRoot}`,
              "",
              "=== STDOUT ===",
              stdout || "(no output)",
              "",
              "=== STDERR ===",
              stderr || "(no error output)",
            ].join("\n"),
          },
        ],
      };
    }

    throw new Error(`Tool ${name} tidak ditemukan`);
  } catch (error: any) {
    return {
      content: [
        {
          type: "text",
          text: `Error executing tool ${name}: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
});

// Run the server using stdio transport
const transport = new StdioServerTransport();
await server.connect(transport);
console.error("🚀 Nouva MCP Server running on stdio transport!");
