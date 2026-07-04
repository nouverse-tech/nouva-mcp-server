import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { exec } from "child_process";
import { promisify } from "util";
import fs from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

const execAsync = promisify(exec);

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

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
      {
        name: "gading_dev_get_guidelines",
        description: "Mendapatkan panduan markdown dinamis untuk kontribusi konten blog gading.dev",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "gading_dev_publish",
        description: "Mempublikasikan perubahan blog gading.dev (git add, commit, push, dan trigger Cloudinary sync)",
        inputSchema: {
          type: "object",
          properties: {
            commitMessage: {
              type: "string",
              description: "Conventional commit message (misal: 'feat: add new post about mcp')",
            },
          },
          required: ["commitMessage"],
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

    if (name === "gading_dev_get_guidelines") {
      const templatePath = path.join(__dirname, "../templates/contributing-guidelines.md");
      const guidelines = await fs.readFile(templatePath, "utf-8");

      return {
        content: [
          {
            type: "text",
            text: guidelines,
          },
        ],
      };
    }

    if (name === "gading_dev_publish") {
      const commitMessage = args?.commitMessage as string;
      const blogRepoPath = "/root/.openclaw/workspace/projects/gading.dev";

      // Run publish sequence in the gading.dev repo
      const steps = [
        `git add .`,
        `git commit -m "${commitMessage.replace(/"/g, '\\"')}"`,
        `git push origin main`,
        `gh workflow run cloudinary.yml --repo gadingnstn/gading.dev`
      ];

      const results: string[] = [];
      for (const step of steps) {
        try {
          const { stdout, stderr } = await execAsync(step, { cwd: blogRepoPath });
          results.push(`$ ${step}\nSTDOUT:\n${stdout.trim() || "(no output)"}\nSTDERR:\n${stderr.trim() || "(no error)"}`);
        } catch (stepErr: any) {
          results.push(`$ ${step}\nFAILED: ${stepErr.message}`);
          return {
            content: [
              {
                type: "text",
                text: `Publish failed at step:\n\n${results.join("\n\n")}`,
              },
            ],
            isError: true,
          };
        }
      }

      return {
        content: [
          {
            type: "text",
            text: `Successfully published changes to gading.dev!\n\n${results.join("\n\n")}`,
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
