import subprocess
from rich.console import Console

console = Console()


def get_git_diff(base_ref, target_ref):
    try:
        # Resolve refs to hashes for clarity
        base_hash = subprocess.check_output(["git", "rev-parse", "--short", base_ref], text=True).strip()
        target_hash = subprocess.check_output(["git", "rev-parse", "--short", target_ref], text=True).strip()
        console.print(f"[Info] 执行 Diff: {base_ref}({base_hash}) ... {target_ref}({target_hash})", style="bold cyan")
        
        # 使用三点对比 (Triple Dot Diff) A...B
        # 找出 A 和 B 的共同祖先，对比 B 和 共同祖先 的差异。
        # 这样可以忽略 A 分支（如 master）后续更新带来的干扰，只关注 B 分支（Feature）的净变更。
        diff_range = f"{base_ref}...{target_ref}"
        console.print(f"[Info] 执行 Diff (Smart Mode): {diff_range}", style="bold cyan")
        
        file_patterns = ["*.java", "*.xml", "*.sql", "*.yml", "*.yaml", "*.properties"]
        # git diff base...target -- files
        cmd_commit = ["git", "diff", diff_range, "--"] + file_patterns
        result_commit = subprocess.run(cmd_commit, capture_output=True, text=True, encoding='utf-8')
        
        if result_commit.returncode != 0:
            console.print(f"[red]Git Diff Error: {result_commit.stderr}[/red]")
            return None

        if result_commit.stdout and result_commit.stdout.strip():
            return result_commit.stdout

        console.print("[Info] 指定版本间未检测到变更。", style="dim")
        return None
    except Exception as e:
        console.print(f"Error: {e}")
        return None


def parse_diff(diff_text):
    files_diff = {}
    current_file = None
    buffer = []
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            if current_file:
                files_diff[current_file] = "\n".join(buffer)
            parts = line.split()
            if len(parts) >= 4:
                raw_filename = parts[-1]
                current_file = raw_filename[2:] if raw_filename.startswith("b/") else raw_filename
                buffer = []
        buffer.append(line)
    if current_file:
        files_diff[current_file] = "\n".join(buffer)
    return files_diff
