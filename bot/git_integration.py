"""Git integration for auto-committing code changes."""
from __future__ import annotations
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def git_commit(file_paths: list[str], commit_message: str) -> tuple[bool, Optional[str]]:
    """
    Commit files to git repository.

    Args:
        file_paths: List of file paths to commit
        commit_message: Commit message

    Returns:
        tuple: (success, error_message)
               - success: True if commit succeeded
               - error_message: Error description if failed, None otherwise
    """
    try:
        # Check if we're in a git repository
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            return False, "Not in a git repository"

        # Stage the files
        for file_path in file_paths:
            result = subprocess.run(
                ["git", "add", "."],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode != 0:
                return False, f"Failed to stage file {file_path}: {result.stderr}"

        # Commit the changes
        result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            # Check if there's nothing to commit
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                logger.info("No changes to commit")
                return True, None
            return False, f"Failed to commit: {result.stderr}"

        logger.info(f"Successfully committed: {commit_message}")
        return True, None

    except FileNotFoundError:
        return False, "Git command not found. Please install git."
    except Exception as e:
        logger.exception(f"Error during git commit: {e}")
        return False, f"Unexpected error: {e}"


def git_remove(file_path: str, commit_message: str) -> tuple[bool, Optional[str]]:
    """
    Remove a file from git repository and commit.

    Args:
        file_path: Path to file to remove
        commit_message: Commit message

    Returns:
        tuple: (success, error_message)
    """
    try:
        # Check if file exists in git
        result = subprocess.run(
            ["git", "ls-files", file_path],
            capture_output=True,
            text=True,
            check=False
        )
        if not result.stdout.strip():
            logger.warning(f"File {file_path} not tracked by git")
            # File not in git, just delete it
            Path(file_path).unlink(missing_ok=True)
            return True, None

        # Remove from git
        result = subprocess.run(
            ["git", "rm", file_path],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            return False, f"Failed to remove file from git: {result.stderr}"

        # Commit the removal
        result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            return False, f"Failed to commit removal: {result.stderr}"

        logger.info(f"Successfully removed and committed: {file_path}")
        return True, None

    except FileNotFoundError:
        return False, "Git command not found. Please install git."
    except Exception as e:
        logger.exception(f"Error during git removal: {e}")
        return False, f"Unexpected error: {e}"


def get_git_status() -> tuple[bool, str]:
    """
    Get current git status.

    Returns:
        tuple: (success, output)
    """
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            return False, result.stderr
        return True, result.stdout
    except Exception as e:
        return False, str(e)
