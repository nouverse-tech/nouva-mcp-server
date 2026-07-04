import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { exec } from "child_process";
import { promisify } from "util";
import fs from "fs/promises";
import path from "path";
import { fileURLToPath, pathToFileURL } from "url";

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
      resources: {},
    },
  }
);

// Map to store dynamic tool handlers
const dynamicToolsMap = new Map<string, { handler: (args: any) => Promise<any>; metadata: any }>();

// Map to store dynamic resources (guidelines)
const dynamicResourcesMap = new Map<string, { name: string; description: string; path: string; uri: string }>();

// Helper to check if file/folder exists
async function exists(p: string): Promise<boolean> {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

// Dynamically scan and load skills (Resources & Tools)
async function loadSkills() {
  // We scan the source directory to find skills, but import from the compiled dist directory
  const srcSkillsDir = path.join(__dirname, "skills");
  const distSkillsDir = path.join(__dirname, "skills"); // since index.js is in dist/, __dirname points to dist/

  if (!(await exists(distSkillsDir))) {
    console.error(`Skills directory not found at ${distSkillsDir}`);
    return;
  }

  const skillFolders = await fs.readdir(distSkillsDir);

  for (const folder of skillFolders) {
    const skillPath = path.join(distSkillsDir, folder);
    const stat = await fs.stat(skillPath);

    if (!stat.isDirectory()) continue;

    // 1. Register SKILL.md as Resource
    // Since SKILL.md is not compiled by tsc, it only exists in src/.
    // Let's resolve the path relative to src/ or dist/
    let skillMdPath = path.join(skillPath, "SKILL.md");
    if (!await exists(skillMdPath)) {
      // If it's running from dist/, SKILL.md is in the src/ counterpart directory
      const srcSkillPath = skillPath.replace("/dist/skills", "/src/skills");
      skillMdPath = path.join(srcSkillPath, "SKILL.md");
    }

    if (await exists(skillMdPath)) {
      const uri = `metadata://skills/${folder}/guidelines`;
      dynamicResourcesMap.set(uri, {
        name: `${folder}-guidelines`,
        description: `Panduan/Guidelines untuk skill ${folder}`,
        path: skillMdPath,
        uri,
      });
      console.error(`Loaded resource guidelines for skill: ${folder}`);
    }

    // 2. Scan and load tools dynamically from tools/ directory
    const toolsDir = path.join(skillPath, "tools");
    if (await exists(toolsDir)) {
      const toolFiles = await fs.readdir(toolsDir);
      for (const file of toolFiles) {
        if (!file.endsWith(".js") && !file.endsWith(".ts")) continue;
        // Only load compiled .js files at runtime if running from dist
        if (file.endsWith(".ts") && __dirname.includes("dist")) continue;
        if (file.endsWith(".js") && !__dirname.includes("dist")) continue;

        const toolFilePath = path.join(toolsDir, file);
        try {
          // Dynamic import using file:// URL for ES Modules compatibility
          const fileUrl = pathToFileURL(toolFilePath).href;
          const toolModule = await import(fileUrl);

          if (toolModule.metadata && typeof toolModule.handler === "function") {
            const toolName = toolModule.metadata.name;
            dynamicToolsMap.set(toolName, {
              handler: toolModule.handler,
              metadata: toolModule.metadata,
            });
            console.error(`Loaded dynamic tool: ${toolName} from skill ${folder}`);
          }
        } catch (err: any) {
          console.error(`Failed to load tool ${file} from skill ${folder}:`, err.message);
        }
      }
    }
  }
}

// Load skills before setting up handlers
await loadSkills();

// Register available tools (Static + Dynamic)
server.setRequestHandler(ListToolsRequestSchema, async () => {
  const staticTools = [
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
  ];

  const dynamicTools = Array.from(dynamicToolsMap.values()).map(t => t.metadata);

  return {
    tools: [...staticTools, ...dynamicTools],
  };
});

// Handle tool execution requests
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    // Check dynamic tools first
    if (dynamicToolsMap.has(name)) {
      const tool = dynamicToolsMap.get(name)!;
      return await tool.handler(args);
    }

    // Fallback to static tools
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

// Register available resources (Guidelines)
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  const resources = Array.from(dynamicResourcesMap.values()).map(r => ({
    uri: r.uri,
    name: r.name,
    description: r.description,
    mimeType: "text/markdown",
  }));

  return {
    resources,
  };
});

// Read resource content
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;

  if (dynamicResourcesMap.has(uri)) {
    const resource = dynamicResourcesMap.get(uri)!;
    const content = await fs.readFile(resource.path, "utf-8");

    return {
      contents: [
        {
          uri,
          mimeType: "text/markdown",
          text: content,
        },
      ],
    };
  }

  throw new Error(`Resource ${uri} tidak ditemukan`);
});

// Run the server using stdio transport
const transport = new StdioServerTransport();
await server.connect(transport);
console.error("🚀 Nouva MCP Server running on stdio transport!");
