import os
import sys
import re
import json
import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configuration Constants
SYNC_LIMIT_DAYS = 1  # Number of days to keep locally before archiving to NAS (e.g. 1 = H-1, 2 = H-2)


def cleanup_local_rina_mentions(memory_dir: str) -> None:
    """Normalize 'Rina' → 'Kak Rina' in all local markdown files."""
    print("🧹 Cleaning up local 'Rina' mentions to 'Kak Rina'...")
    if not os.path.exists(memory_dir):
        return
    pattern = re.compile(r"\b(Kak\s+)?Rina\b", re.IGNORECASE)

    for filename in os.listdir(memory_dir):
        if not filename.endswith(".md") or filename.startswith("."):
            continue
        file_path = os.path.join(memory_dir, filename)
        if not os.path.isfile(file_path):
            continue
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            updated = content.replace("[[Rina]]", "[[Kak Rina]]")
            updated = pattern.sub(lambda m: "Kak Rina", updated)
            if updated != content:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(updated)
                print(f"  ✅ Normalized names in local file: {filename}")
        except Exception as e:
            print(f"  ⚠️ Error cleaning up names in {filename}: {e}")


def _is_file_empty(file_path: str) -> bool:
    try:
        if os.path.getsize(file_path) == 0:
            return True
        with open(file_path, "r", encoding="utf-8") as f:
            return not f.read().strip()
    except Exception:
        return False


def archive_and_clean_local(memory_dir: str, synced_filenames: list, nas) -> None:
    """Inject spine/parent links into files, transfer them to NAS, then delete locally."""
    from memory_sync.memory_summary_sync import get_previous_date_local_or_nas

    dates = [f[:10] for f in synced_filenames]
    if not dates:
        return

    print("🚚 Transferring memory files to NAS...")
    for filename in synced_filenames:
        file_path = os.path.join(memory_dir, filename)
        if not os.path.exists(file_path):
            continue
        try:
            date_str = filename[:10]
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                file_content = f.read()

            file_content = re.sub(r"\[\[reply_to(_current|:\w+)\]\]", "", file_content)

            if len(filename) == 13:  # Daily Note YYYY-MM-DD.md
                file_content = re.compile(r"\n\n«\s*\[\[\d{4}-\d{2}-\d{2}\]\]\s*\|\s*Timeline\s*Spine.*", re.IGNORECASE).sub("", file_content).strip()
                file_content = re.sub(r"\n\n\[\[\d{4}-\d{2}-\d{2}\.summary\|📄 View Summary\]\]", "", file_content).strip()
                prev_date = get_previous_date_local_or_nas(date_str, memory_dir, nas)
                if prev_date:
                    file_content += f"\n\n« [[{prev_date}]] | Timeline Spine | [[{date_str}.summary|📄 View Summary]]"
                else:
                    file_content += f"\n\n[[{date_str}.summary|📄 View Summary]]"

            elif len(filename) >= 18:  # Raw transcript YYYY-MM-DD-XXXX.md
                file_content = re.compile(r"Parent\s*Day:\s*\[\[.*?\]\]", re.IGNORECASE).sub("", file_content).strip()
                lines = file_content.splitlines()
                header_idx = next((i for i, l in enumerate(lines) if l.startswith(("# Session:", "# Raw Session:"))), -1)
                parent_link = f"Parent Day: [[{date_str}]]"
                if header_idx != -1:
                    lines.insert(header_idx + 1, parent_link)
                    lines.insert(header_idx + 2, "")
                else:
                    lines = [parent_link, ""] + lines
                file_content = "\n".join(lines).strip()

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_content)

            if nas.copy_to(file_path, f"daily_sessions/{date_str}", filename):
                os.remove(file_path)
                print(f"✅ Transferred and deleted local file: {filename}")
            else:
                print(f"❌ Failed to transfer {filename} to NAS")
        except Exception as e:
            print(f"❌ Exception transferring {filename}: {e}")

    # Transfer corresponding summaries to NAS
    summaries_dir = os.path.join(memory_dir, "_summaries")
    if os.path.exists(summaries_dir):
        for d in sorted(set(dates)):
            summary_file = f"{d}.summary.md"
            summary_path = os.path.join(summaries_dir, summary_file)
            if os.path.exists(summary_path):
                try:
                    if nas.copy_to(summary_path, "daily_sessions/_summaries", summary_file):
                        os.remove(summary_path)
                        print(f"✅ Transferred and deleted summary: {summary_file}")
                    else:
                        print(f"❌ Failed to transfer summary {summary_file} to NAS")
                except Exception as e:
                    print(f"❌ Exception transferring summary {summary_file}: {e}")


def sync_memory_logs(active_memory_dir: str, nas) -> None:
    """Archive daily notes and raw transcripts older than 2 days to NAS."""
    print("--- Archiving Memory Logs (No RAG upload) ---")

    state_path = os.path.join(os.path.dirname(__file__), "../memory_sync-state.json")
    last_synced_str = "1970-01-01"
    if os.path.exists(state_path):
        try:
            with open(state_path, "r") as f:
                last_synced_str = json.load(f).get("last_synced_date", "1970-01-01")
        except Exception as e:
            print(f"⚠️ Error reading state file: {e}")

    try:
        last_synced_date = datetime.datetime.strptime(last_synced_str, "%Y-%m-%d").date()
    except Exception:
        last_synced_date = datetime.date(1970, 1, 1)

    limit = datetime.date.today() - datetime.timedelta(days=SYNC_LIMIT_DAYS)
    memory_dir = active_memory_dir

    if not os.path.exists(memory_dir):
        print("❌ Memory directory not found.")
        return

    all_files = os.listdir(memory_dir)

    # Gather and filter daily notes
    to_sync = []
    for filename in [f for f in all_files if f.endswith(".md") and len(f) == 13]:
        try:
            fd = datetime.datetime.strptime(filename[:-3], "%Y-%m-%d").date()
            if last_synced_date < fd <= limit:
                date_str = filename[:-3]
                summary_file = f"{date_str}.summary.md"
                local_summary_path = os.path.join(memory_dir, "_summaries", summary_file)
                if not os.path.exists(local_summary_path):
                    print(f"⚠️ Skipping archive for {date_str} because summary is missing. Will retry summary generation next run.")
                    continue
                to_sync.append((fd, filename))
        except ValueError:
            continue
    to_sync.sort(key=lambda x: x[0])

    # Gather raw transcripts
    raw_files_clean = []
    for filename in [f for f in all_files if f.endswith(".md") and len(f) >= 18 and f[10] == "-"]:
        try:
            fd = datetime.datetime.strptime(filename[:10], "%Y-%m-%d").date()
            if fd > limit:
                continue
            date_str = filename[:10]
            summary_file = f"{date_str}.summary.md"
            local_summary_path = os.path.join(memory_dir, "_summaries", summary_file)
            if not os.path.exists(local_summary_path):
                continue
        except ValueError:
            continue
        file_path = os.path.join(memory_dir, filename)
        if _is_file_empty(file_path):
            try:
                os.remove(file_path)
                print(f"🗑️ Deleted empty raw file locally: {filename}")
            except Exception as e:
                print(f"⚠️ Failed to delete empty raw file {filename}: {e}")
        else:
            raw_files_clean.append(filename)

    synced_files = []
    for file_date, filename in to_sync:
        file_path = os.path.join(memory_dir, filename)
        date_str = file_date.strftime("%Y-%m-%d")

        if _is_file_empty(file_path):
            print(f"⏭️ File {filename} is empty. Deleting locally.")
            try:
                os.remove(file_path)
                print(f"🗑️ Deleted local empty memory file: {filename}")
            except Exception as e:
                print(f"⚠️ Failed to delete empty local file {filename}: {e}")
        else:
            synced_files.append(filename)

        try:
            with open(state_path, "w") as f:
                json.dump({"last_synced_date": date_str}, f, indent=2)
            print(f"📝 Sync state updated to: {date_str}")
        except Exception as e:
            print(f"❌ Error writing state file: {e}")

    if synced_files:
        print(f"✅ Processed {len(synced_files)} daily logs for archiving.")
    else:
        print("⏭️ No new daily memory logs to archive.")

    combined = synced_files + raw_files_clean
    if combined:
        archive_and_clean_local(memory_dir, combined, nas)
    else:
        print("⏭️ No memory logs to archive.")
