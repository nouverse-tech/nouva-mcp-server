import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

export const metadata = {
  name: "generate_morning_report",
  description: "Menghasilkan laporan kesehatan harian untuk infrastruktur Nouverse (K3s, Docker, CPU/RAM, NAS, Backups, Gmail, OpenClaw)",
  inputSchema: {
    type: "object",
    properties: {},
  },
};

export async function handler() {
  const scriptPath = "/root/.openclaw/workspace/skills/morning-report/scripts/generate_report.py";
  try {
    const { stdout, stderr } = await execAsync(`python3 ${scriptPath}`);
    return {
      content: [
        {
          type: "text",
          text: stdout.trim() || stderr.trim() || "(no output)",
        },
      ],
    };
  } catch (error: any) {
    return {
      content: [
        {
          type: "text",
          text: `Gagal menghasilkan morning report: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
}
