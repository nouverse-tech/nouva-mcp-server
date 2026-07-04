import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

export const metadata = {
  name: "gading_dev_publish",
  description: "Meng-merge Pull Request (PR) yang sudah disetujui ke main, lalu menjalankan workflow sync Cloudinary",
  inputSchema: {
    type: "object",
    properties: {
      prNumber: {
        type: "number",
        description: "Nomor Pull Request (optional, jika kosong akan mencari PR dari branch saat ini)",
      },
      branchName: {
        type: "string",
        description: "Nama branch asal PR (optional)",
      },
    },
  },
};

export async function handler(args: any) {
  const blogRepoPath = "/root/.openclaw/workspace/projects/gading.dev";
  let prTarget = "";

  try {
    if (args.prNumber) {
      prTarget = String(args.prNumber);
    } else if (args.branchName) {
      // Find PR number by branch name
      const { stdout } = await execAsync(`gh pr list --head "${args.branchName}" --json number --jq ".[0].number"`, { cwd: blogRepoPath });
      prTarget = stdout.trim();
      if (!prTarget) {
        throw new Error(`Tidak ditemukan PR aktif untuk branch ${args.branchName}`);
      }
    } else {
      // Find PR number for current branch
      const { stdout: branchStdout } = await execAsync(`git branch --show-current`, { cwd: blogRepoPath });
      const currentBranch = branchStdout.trim();
      if (currentBranch === "main" || currentBranch === "master") {
        throw new Error("Anda sedang berada di branch main/master. Harap tentukan prNumber atau branchName secara eksplisit.");
      }

      const { stdout: prStdout } = await execAsync(`gh pr view --json number --jq ".number"`, { cwd: blogRepoPath });
      prTarget = prStdout.trim();
      if (!prTarget) {
        throw new Error(`Tidak ditemukan PR aktif untuk branch saat ini (${currentBranch})`);
      }
    }

    // Run publish sequence: merge PR, checkout main, pull, trigger Cloudinary sync
    const steps = [
      `gh pr merge ${prTarget} --merge --delete-branch`,
      `git checkout main`,
      `git pull origin main`,
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
          text: `Successfully merged PR #${prTarget} and triggered Cloudinary sync!\n\n${results.join("\n\n")}`,
        },
      ],
    };
  } catch (error: any) {
    return {
      content: [
        {
          type: "text",
          text: `Publish/Merge failed: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
}
