import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

export const metadata = {
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
};

export async function handler(args: any) {
  const commitMessage = args.commitMessage as string;
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
    const { stdout, stderr } = await execAsync(step, { cwd: blogRepoPath });
    results.push(`$ ${step}\nSTDOUT:\n${stdout.trim() || "(no output)"}\nSTDERR:\n${stderr.trim() || "(no error)"}`);
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
