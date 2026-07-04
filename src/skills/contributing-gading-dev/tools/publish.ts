import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

export const metadata = {
  name: "gading_dev_publish",
  description: "Mempublikasikan perubahan blog gading.dev dengan membuat branch baru dan Pull Request (PR) ke main",
  inputSchema: {
    type: "object",
    properties: {
      commitMessage: {
        type: "string",
        description: "Conventional commit message (misal: 'feat: add new post about mcp')",
      },
      branchName: {
        type: "string",
        description: "Nama branch baru (optional, default auto-generated dari commit message)",
      },
      prBody: {
        type: "string",
        description: "Deskripsi isi Pull Request (optional)",
      },
    },
    required: ["commitMessage"],
  },
};

export async function handler(args: any) {
  const commitMessage = args.commitMessage as string;
  const prBody = args.prBody || "Draft content contribution via Nouva MCP Server.";
  const blogRepoPath = "/root/.openclaw/workspace/projects/gading.dev";

  // Generate a safe branch name from commit message if not provided
  let branchName = args.branchName as string;
  if (!branchName) {
    const cleanMsg = commitMessage
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, "")
      .trim()
      .replace(/\s+/g, "-");
    branchName = `content/${cleanMsg || "new-post-" + Date.now()}`;
  }

  // Run publish sequence in the gading.dev repo using branching & PR
  const steps = [
    `git checkout main`,
    `git pull origin main`,
    `git checkout -b ${branchName}`,
    `git add .`,
    `git commit -m "${commitMessage.replace(/"/g, '\\"')}"`,
    `git push -u origin ${branchName}`,
    `gh pr create --title "${commitMessage.replace(/"/g, '\\"')}" --body "${prBody.replace(/"/g, '\\"')}" --reviewer gadingnst --assignee @me --label feat`
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
            text: `Publish/PR creation failed at step:\n\n${results.join("\n\n")}`,
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
        text: `Successfully created Pull Request for gading.dev!\n\n${results.join("\n\n")}`,
      },
    ],
  };
}
