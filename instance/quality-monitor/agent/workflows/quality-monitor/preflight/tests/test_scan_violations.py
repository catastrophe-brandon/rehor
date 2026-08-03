"""Unit tests for quality monitor preflight script."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile

import pytest

# Add preflight to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent.parent.parent / "presets" / "shared" / "preflight"))
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import after path setup
import importlib.util
spec = importlib.util.spec_from_file_location(
    "scan_violations",
    Path(__file__).parent.parent / "01-scan-prs-for-violations.py"
)
scan_violations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan_violations)


@pytest.fixture
def temp_state_file(tmp_path):
    """Create temporary state file."""
    state_file = tmp_path / "data" / "preflight-state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    return state_file


@pytest.fixture
def mock_state_operations(temp_state_file, monkeypatch):
    """Mock state file operations."""
    def mock_load_state():
        if temp_state_file.exists():
            return json.loads(temp_state_file.read_text())
        return {}

    def mock_save_state(updates):
        state = mock_load_state()
        state.update(updates)
        temp_state_file.write_text(json.dumps(state, default=str))

    monkeypatch.setattr("scan_violations.load_state", mock_load_state)
    monkeypatch.setattr("scan_violations.save_state", mock_save_state)

    return temp_state_file


class TestGetRecentMergedPRs:
    """Test get_recent_merged_prs with different timestamp scenarios."""

    def test_first_run_no_timestamp(self):
        """Test first run with no previous scan timestamp."""
        # When no timestamp provided, should use 48-hour fallback
        with patch("scan_violations.subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([
                    {
                        "number": 100,
                        "title": "Test PR",
                        "url": "https://github.com/test/repo/pull/100",
                        "mergedAt": datetime.now().isoformat() + "Z",
                        "author": {"login": "testuser"},
                        "files": []
                    }
                ]),
                text=True
            )

            result = scan_violations.get_recent_merged_prs("test/repo", since_timestamp=None)

            assert len(result) == 1
            assert result[0]["number"] == 100
            # Verify gh CLI called with correct params
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "gh" in args
            assert "pr" in args
            assert "list" in args

    def test_normal_run_with_valid_timestamp(self):
        """Test normal run with valid timestamp from previous scan."""
        # Create timestamp from 2 hours ago
        two_hours_ago = (datetime.now() - timedelta(hours=2)).isoformat()

        with patch("scan_violations.subprocess.run") as mock_run:
            # PR merged 1 hour ago (within window)
            recent_pr = {
                "number": 200,
                "title": "Recent PR",
                "url": "https://github.com/test/repo/pull/200",
                "mergedAt": (datetime.now() - timedelta(hours=1)).isoformat() + "Z",
                "author": {"login": "testuser"},
                "files": []
            }
            # PR merged 3 hours ago (before window)
            old_pr = {
                "number": 199,
                "title": "Old PR",
                "url": "https://github.com/test/repo/pull/199",
                "mergedAt": (datetime.now() - timedelta(hours=3)).isoformat() + "Z",
                "author": {"login": "testuser"},
                "files": []
            }

            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([recent_pr, old_pr]),
                text=True
            )

            result = scan_violations.get_recent_merged_prs("test/repo", since_timestamp=two_hours_ago)

            # Should only return PR from last 2 hours
            assert len(result) == 1
            assert result[0]["number"] == 200

    def test_invalid_timestamp_format(self, capsys):
        """Test handling of invalid timestamp format."""
        with patch("scan_violations.subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([]),
                text=True
            )

            # Invalid timestamp should fall back to 48h window and log warning
            result = scan_violations.get_recent_merged_prs("test/repo", since_timestamp="invalid-timestamp")

            # Should not crash, returns empty list
            assert isinstance(result, list)

            # Should log warning to stderr
            captured = capsys.readouterr()
            assert "WARNING" in captured.err
            assert "invalid-timestamp" in captured.err

    def test_timestamp_with_z_suffix(self):
        """Test timestamp parsing with Z suffix (GitHub format)."""
        timestamp = "2026-08-03T10:00:00Z"

        with patch("scan_violations.subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([]),
                text=True
            )

            result = scan_violations.get_recent_merged_prs("test/repo", since_timestamp=timestamp)

            # Should parse without error
            assert isinstance(result, list)

    def test_gh_cli_failure(self):
        """Test handling of gh CLI command failure."""
        with patch("scan_violations.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", text=True)

            result = scan_violations.get_recent_merged_prs("test/repo")

            # Should return empty list on failure
            assert result == []

    def test_gh_cli_timeout(self):
        """Test handling of gh CLI timeout."""
        with patch("scan_violations.subprocess.run") as mock_run:
            from subprocess import TimeoutExpired
            mock_run.side_effect = TimeoutExpired("gh", 30)

            result = scan_violations.get_recent_merged_prs("test/repo")

            # Should return empty list on timeout
            assert result == []


class TestHasBotCommented:
    """Test has_bot_commented deduplication logic."""

    def test_no_bot_comment(self):
        """Test PR with no bot comments."""
        with patch("scan_violations.subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps({
                    "comments": [
                        {
                            "author": {"login": "human-user"},
                            "body": "LGTM"
                        }
                    ]
                }),
                text=True
            )

            result = scan_violations.has_bot_commented("test/repo", 100)

            assert result is False

    def test_bot_comment_with_signature(self):
        """Test PR with bot comment containing signature."""
        with patch("scan_violations.subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps({
                    "comments": [
                        {
                            "author": {"login": "human-user"},
                            "body": "Great work!"
                        },
                        {
                            "author": {"login": "rehor-bot"},
                            "body": "I AM THE LAW! Empty catch blocks detected.\n\nRehor Quality Monitor"
                        }
                    ]
                }),
                text=True
            )

            result = scan_violations.has_bot_commented("test/repo", 100)

            assert result is True

    def test_bot_comment_rehor_signature(self):
        """Test detection of Rehor Quality Monitor signature."""
        with patch("scan_violations.subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps({
                    "comments": [
                        {
                            "author": {"login": "user"},
                            "body": "This was flagged by Rehor Quality Monitor"
                        }
                    ]
                }),
                text=True
            )

            result = scan_violations.has_bot_commented("test/repo", 100)

            assert result is True

    def test_bot_username_detection(self):
        """Test detection via bot username patterns."""
        with patch("scan_violations.subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps({
                    "comments": [
                        {
                            "author": {"login": "github-actions[bot]"},
                            "body": "Some comment"
                        }
                    ]
                }),
                text=True
            )

            result = scan_violations.has_bot_commented("test/repo", 100)

            # Note: Currently checks for "rehor" in username
            # This test documents the behavior - may want to expand bot detection
            assert result is False  # github-actions[bot] doesn't contain "rehor"


class TestStateManagement:
    """Test state file management for timestamp tracking."""

    def test_state_saved_after_successful_scan(self, mock_state_operations):
        """Test that state is saved with current timestamp after scan."""
        with patch("scan_violations.get_capacity") as mock_capacity, \
             patch("scan_violations.load_project_repos") as mock_repos, \
             patch("scan_violations.output_result") as mock_output:

            mock_capacity.return_value = (0, 10)  # Not at capacity
            mock_repos.return_value = {}  # No repos to scan

            scan_violations.main()

            # Check that state was saved with timestamp
            state = json.loads(mock_state_operations.read_text())
            assert "last_merge_check_scan" in state

            # Verify timestamp is recent (within last minute)
            saved_time = datetime.fromisoformat(state["last_merge_check_scan"])
            assert (datetime.now() - saved_time).total_seconds() < 60

    def test_first_run_creates_state(self, mock_state_operations):
        """Test that first run creates state file."""
        # Ensure state file doesn't exist
        if mock_state_operations.exists():
            mock_state_operations.unlink()

        with patch("scan_violations.get_capacity") as mock_capacity, \
             patch("scan_violations.load_project_repos") as mock_repos, \
             patch("scan_violations.output_result") as mock_output:

            mock_capacity.return_value = (0, 10)
            mock_repos.return_value = {}

            scan_violations.main()

            # State file should now exist
            assert mock_state_operations.exists()
            state = json.loads(mock_state_operations.read_text())
            assert "last_merge_check_scan" in state

    def test_subsequent_run_uses_previous_timestamp(self, mock_state_operations):
        """Test that subsequent runs use timestamp from previous scan."""
        # Set up initial state with timestamp from 1 hour ago
        initial_timestamp = (datetime.now() - timedelta(hours=1)).isoformat()
        mock_state_operations.write_text(json.dumps({
            "last_merge_check_scan": initial_timestamp
        }))

        with patch("scan_violations.get_capacity") as mock_capacity, \
             patch("scan_violations.load_project_repos") as mock_repos, \
             patch("scan_violations.upstream_repo") as mock_upstream, \
             patch("scan_violations.get_recent_merged_prs") as mock_get_prs, \
             patch("scan_violations.output_result") as mock_output:

            mock_capacity.return_value = (0, 10)
            mock_repos.return_value = {"test-repo": {}}
            mock_upstream.return_value = ("test/repo", "github")
            mock_get_prs.return_value = []  # No PRs

            scan_violations.main()

            # Verify get_recent_merged_prs was called with the previous timestamp
            mock_get_prs.assert_called_once()
            call_kwargs = mock_get_prs.call_args[1]
            assert call_kwargs["since_timestamp"] == initial_timestamp


class TestScanDiffForViolations:
    """Test violation pattern detection in diffs."""

    def test_detect_empty_catch_block(self):
        """Test detection of empty catch blocks."""
        diff = """
diff --git a/test.js b/test.js
+++ b/test.js
@@ -10,0 +11,3 @@
+try {
+  doSomething();
+} catch (e) { }
"""
        violations = scan_violations.scan_diff_for_violations(diff)

        swallowed_errors = [v for v in violations if v["pattern"] == "swallowed_errors"]
        assert len(swallowed_errors) > 0
        assert swallowed_errors[0]["severity"] == "high"

    def test_detect_console_log(self):
        """Test detection of console.log statements."""
        diff = """
diff --git a/app.js b/app.js
+++ b/app.js
@@ -5,0 +6,1 @@
+console.log('debug info');
"""
        violations = scan_violations.scan_diff_for_violations(diff)

        console_logs = [v for v in violations if v["pattern"] == "console_log"]
        assert len(console_logs) > 0
        assert console_logs[0]["severity"] == "medium"

    def test_detect_todo_comment(self):
        """Test detection of TODO comments."""
        diff = """
diff --git a/code.py b/code.py
+++ b/code.py
@@ -8,0 +9,1 @@
+// TODO: refactor this
"""
        violations = scan_violations.scan_diff_for_violations(diff)

        todos = [v for v in violations if v["pattern"] == "todo_comments"]
        assert len(todos) > 0
        assert todos[0]["severity"] == "low"

    def test_detect_magic_numbers(self):
        """Test detection of hard-coded timeout values."""
        diff = """
diff --git a/test.js b/test.js
+++ b/test.js
@@ -15,0 +16,1 @@
+setTimeout(5000);
"""
        violations = scan_violations.scan_diff_for_violations(diff)

        magic_numbers = [v for v in violations if v["pattern"] == "magic_numbers"]
        assert len(magic_numbers) > 0
        assert magic_numbers[0]["severity"] == "high"

    def test_only_scans_added_lines(self):
        """Test that violations are only detected in added lines (+ prefix)."""
        diff = """
diff --git a/test.js b/test.js
+++ b/test.js
@@ -10,1 +11,2 @@
-console.log('old');
+const logger = createLogger();
 existingLine();
"""
        violations = scan_violations.scan_diff_for_violations(diff)

        # Should not detect console.log in removed line
        console_logs = [v for v in violations if v["pattern"] == "console_log"]
        assert len(console_logs) == 0

    def test_no_violations_in_clean_diff(self):
        """Test that clean code produces no violations."""
        diff = """
diff --git a/app.js b/app.js
+++ b/app.js
@@ -10,0 +11,3 @@
+function greet(name) {
+  return `Hello, ${name}!`;
+}
"""
        violations = scan_violations.scan_diff_for_violations(diff)

        assert len(violations) == 0
