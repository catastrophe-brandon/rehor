#!/usr/bin/env python3
"""Scan recent PRs for code quality violations."""

import subprocess
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from common import load_project_repos, upstream_repo, output_result, get_capacity, load_state, save_state

# Quality violation patterns to detect
VIOLATION_PATTERNS = {
    "swallowed_errors": {
        "regex": r'catch\s*\([^)]*\)\s*\{\s*(?://[^\n]*\n)?\s*\}',
        "severity": "high",
        "message": "Empty catch block detected - errors are being swallowed",
        "dredd_phrase": [
            "I AM THE LAW! Empty catch blocks are a crime against justice!",
            "You have been judged! The sentence for swallowing errors: REFACTOR!",
            "Guilty of code crimes! Empty catch blocks will not be tolerated!",
        ],
        "recommendation": "Handle the error appropriately or at minimum log it"
    },
    "console_log": {
        "regex": r'console\.(log|debug|info)\(',
        "severity": "medium",
        "message": "Console.log statement found in production code",
        "dredd_phrase": [
            "The law is clear: no console.log statements in production!",
            "Justice demands proper logging! Remove this console statement!",
            "I am the LAW! Console logs are for debugging only!",
        ],
        "recommendation": "Use a proper logging framework or remove debug statements"
    },
    "todo_comments": {
        "regex": r'//\s*TODO(?:\s*:|\s+)',
        "severity": "low",
        "message": "TODO comment detected",
        "dredd_phrase": [
            "The law requires action, not TODO comments!",
            "Justice delayed is justice denied! Complete this TODO!",
            "I AM THE LAW! TODOs must be tracked or completed!",
        ],
        "recommendation": "Create a ticket for this work or complete it now"
    },
    "magic_numbers": {
        "regex": r'(?<![a-zA-Z0-9_])(sleep|setTimeout|wait)\s*\(\s*\d{3,}',
        "severity": "high",
        "message": "Hard-coded timeout/sleep value detected",
        "dredd_phrase": [
            "GUILTY of magic numbers! The law demands named constants!",
            "I judge you! Hard-coded timeouts are a crime!",
            "The law is the law! Extract this magic number to a constant!",
        ],
        "recommendation": "Extract magic numbers to named constants"
    },
    "force_push": {
        "regex": r'git\s+push.*--force(?!-with-lease)',
        "severity": "high",
        "message": "Force push without --force-with-lease detected",
        "dredd_phrase": [
            "I AM THE LAW! Force pushing without lease is DANGEROUS!",
            "GUILTY! The law requires --force-with-lease for safety!",
            "Justice demands safer git operations! Use --force-with-lease!",
        ],
        "recommendation": "Use --force-with-lease instead of --force"
    }
}

# Load Judge Dredd images and phrases from config file
def load_dredd_config():
    """Load Dredd images and phrases from JSON config."""
    config_path = Path(__file__).parent.parent.parent.parent / "dredd-images.json"
    try:
        with open(config_path) as f:
            return json.load(f)
    except Exception:
        # Fallback to hardcoded defaults
        return {
            "dredd_images": [
                {"url": "https://i.imgur.com/vB9B5.gif", "type": "classic"}
            ],
            "phrases_by_violation": {}
        }

DREDD_CONFIG = load_dredd_config()
DREDD_IMAGES = [img["url"] for img in DREDD_CONFIG.get("dredd_images", [])]


def clone_repo_if_needed(repo_name, repo_config):
    """Clone repository if not already present."""
    repo_path = Path("repos") / repo_name
    if repo_path.exists():
        return repo_path

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_config["upstream"], str(repo_path)],
            capture_output=True,
            timeout=120
        )
        return repo_path
    except subprocess.TimeoutExpired:
        return None


def has_bot_commented(org_repo, pr_number):
    """Check if the bot has already commented on this PR."""
    try:
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number),
             "--repo", org_repo,
             "--json", "comments"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return False

        data = json.loads(result.stdout)
        comments = data.get("comments", [])

        # Check if any comment is from our bot (contains our signature)
        for comment in comments:
            body = comment.get("body", "")
            author = comment.get("author", {}).get("login", "")

            # Check for bot signature in comment or bot username
            if "Rehor Quality Monitor" in body or "I AM THE LAW" in body:
                return True

            # Also check if author matches bot username patterns
            if "[bot]" in author.lower() or "rehor" in author.lower():
                return True

        return False

    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return False


def get_recent_merged_prs(org_repo, since_timestamp=None):
    """Get PRs merged since the given timestamp (or last 48h if none).

    Args:
        org_repo: Repository in org/repo format
        since_timestamp: ISO timestamp from last scan, or None for first run

    Returns:
        List of PR objects merged since the timestamp
    """
    # Handle first run or missing timestamp - use 48h fallback window
    if not since_timestamp:
        since = datetime.now() - timedelta(hours=48)
    else:
        try:
            # Parse ISO timestamp from state, handle both Z and +00:00 formats
            since = datetime.fromisoformat(since_timestamp.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            # Invalid timestamp format - fall back to 48h window
            print(f"WARNING: Invalid timestamp '{since_timestamp}', using 48h fallback", file=sys.stderr)
            since = datetime.now() - timedelta(hours=48)

    try:
        result = subprocess.run(
            ["gh", "pr", "list",
             "--repo", org_repo,
             "--state", "merged",
             "--limit", "20",
             "--json", "number,title,url,mergedAt,author,files"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return []

        prs = json.loads(result.stdout)
        recent = [
            pr for pr in prs
            if datetime.fromisoformat(pr["mergedAt"].replace("Z", "+00:00")) > since
        ]

        return recent

    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def get_pr_diff(org_repo, pr_number):
    """Get the diff for a PR."""
    try:
        result = subprocess.run(
            ["gh", "pr", "diff", str(pr_number), "--repo", org_repo],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            return result.stdout
        return None

    except subprocess.TimeoutExpired:
        return None


def scan_diff_for_violations(diff_content):
    """Scan a diff for quality violations."""
    violations = []

    if not diff_content:
        return violations

    # Parse diff to get added lines with context
    current_file = None
    current_line = 0

    for line in diff_content.split('\n'):
        # Track which file we're in
        if line.startswith('diff --git'):
            match = re.search(r'b/(.+)$', line)
            if match:
                current_file = match.group(1)
                current_line = 0

        # Track line numbers
        elif line.startswith('@@'):
            match = re.search(r'\+(\d+)', line)
            if match:
                current_line = int(match.group(1))

        # Only check added lines (starting with +)
        elif line.startswith('+') and not line.startswith('+++'):
            current_line += 1
            line_content = line[1:]  # Remove the + prefix

            # Check each violation pattern
            for pattern_name, pattern_def in VIOLATION_PATTERNS.items():
                if re.search(pattern_def["regex"], line_content, re.MULTILINE):
                    violations.append({
                        "pattern": pattern_name,
                        "severity": pattern_def["severity"],
                        "message": pattern_def["message"],
                        "dredd_phrases": pattern_def["dredd_phrase"],
                        "recommendation": pattern_def["recommendation"],
                        "file": current_file,
                        "line": current_line,
                        "snippet": line_content.strip()[:100]
                    })

    return violations


def main():
    """Main preflight execution."""
    # Check capacity
    active_n, max_n = get_capacity()
    if active_n >= max_n:
        output_result("skip", f"At capacity ({active_n}/{max_n})")
        return

    # Load state to get last successful scan timestamp
    # On first run (new bot instance), last_scan will be None and we'll use 48h fallback
    state = load_state()
    last_scan = state.get("last_merge_check_scan")

    repos = load_project_repos()
    all_violations = {}

    # Scan repos for merged PRs since last scan (or last 48h if first run)
    for repo_name in list(repos.keys())[:5]:  # Limit to first 5 repos for now
        upstream, host = upstream_repo(repo_name)
        if not upstream or host != "github":
            continue

        # Get PRs merged since last scan
        recent_prs = get_recent_merged_prs(upstream, since_timestamp=last_scan)

        for pr in recent_prs:
            # Skip if we've already commented on this PR
            if has_bot_commented(upstream, pr["number"]):
                continue

            # Get PR diff
            diff = get_pr_diff(upstream, pr["number"])
            if not diff:
                continue

            # Scan for violations
            violations = scan_diff_for_violations(diff)

            if violations:
                pr_key = f"{repo_name}#{pr['number']}"
                all_violations[pr_key] = {
                    "repo": repo_name,
                    "upstream": upstream,
                    "pr_number": pr["number"],
                    "pr_title": pr["title"],
                    "pr_url": pr["url"],
                    "author": pr.get("author", {}).get("login", "unknown"),
                    "merged_at": pr["mergedAt"],
                    "violations": violations
                }

    # Update state with current timestamp for next run
    current_timestamp = datetime.now().isoformat()
    save_state({"last_merge_check_scan": current_timestamp})

    if not all_violations:
        output_result("skip", "No quality violations found in recent PRs")
        return

    # Format results for AI
    total_violations = sum(len(pr_data["violations"]) for pr_data in all_violations.values())
    content = f"# Quality Violations in Recently Merged PRs\n\n"
    content += f"Found {total_violations} violations across {len(all_violations)} PRs:\n\n"

    for pr_key, pr_data in all_violations.items():
        content += f"## {pr_data['repo']} PR #{pr_data['pr_number']}: {pr_data['pr_title']}\n\n"
        content += f"- **URL:** {pr_data['pr_url']}\n"
        content += f"- **Author:** @{pr_data['author']}\n"
        content += f"- **Merged:** {pr_data['merged_at']}\n"
        content += f"- **Violations:** {len(pr_data['violations'])}\n\n"

        # Group by severity
        by_severity = {"high": [], "medium": [], "low": []}
        for v in pr_data["violations"]:
            by_severity[v["severity"]].append(v)

        for severity in ["high", "medium", "low"]:
            items = by_severity[severity]
            if items:
                content += f"### {severity.upper()} Severity ({len(items)})\n\n"
                for violation in items[:3]:  # Show first 3 per severity
                    content += f"**{violation['message']}**\n"
                    content += f"- Pattern: `{violation['pattern']}`\n"
                    content += f"- Location: `{violation['file']}:{violation['line']}`\n"
                    content += f"- Code: `{violation['snippet']}`\n"
                    content += f"- Fix: {violation['recommendation']}\n\n"

                if len(items) > 3:
                    content += f"... and {len(items) - 3} more {severity} issues\n\n"

    # Add metadata for the skill to use
    content += "\n---\n## PR Violation Data (JSON)\n\n"
    content += "```json\n"
    content += json.dumps(all_violations, indent=2)
    content += "\n```\n"

    output_result("start", content)


if __name__ == "__main__":
    main()
