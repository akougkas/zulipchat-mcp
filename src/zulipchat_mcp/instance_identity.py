"""Instance identity system for multi-project Claude Code sessions."""

import hashlib
import json
import os
import platform
import socket
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class InstanceIdentity:
    """Manages unique identity for each Claude Code instance."""

    def __init__(self):
        """Initialize instance identity manager."""
        self.identity_file = Path.home() / ".claude" / "instance_identity.json"
        self.identity_file.parent.mkdir(parents=True, exist_ok=True)
        self.identity = self._load_or_create_identity()

    def _get_project_info(self) -> dict[str, Any]:
        """Detect project information from environment."""
        project_info = {
            "name": "unknown",
            "path": None,
            "type": None,
            "git_repo": None,
            "git_branch": None,
        }

        # Try to detect from current working directory
        cwd = Path.cwd()
        project_info["path"] = str(cwd)

        # Try to detect project name from directory
        project_info["name"] = cwd.name

        # Check for Git repository
        git_dir = self._find_git_root(cwd)
        if git_dir:
            project_info["git_repo"] = str(git_dir)
            project_info["name"] = git_dir.name

            # Try to get current branch
            try:
                head_file = git_dir / ".git" / "HEAD"
                if head_file.exists():
                    ref = head_file.read_text().strip()
                    if ref.startswith("ref: refs/heads/"):
                        project_info["git_branch"] = ref.replace("ref: refs/heads/", "")
            except:
                pass

        # Detect project type from files
        if (cwd / "package.json").exists():
            project_info["type"] = "nodejs"
            # Try to get project name from package.json
            try:
                with open(cwd / "package.json") as f:
                    pkg = json.load(f)
                    if "name" in pkg:
                        project_info["name"] = pkg["name"]
            except:
                pass
        elif (cwd / "pyproject.toml").exists():
            project_info["type"] = "python"
            # Try to get project name from pyproject.toml
            try:
                import tomllib

                with open(cwd / "pyproject.toml", "rb") as f:
                    data = tomllib.load(f)
                    if "project" in data and "name" in data["project"]:
                        project_info["name"] = data["project"]["name"]
            except:
                # Fall back to simple parsing if tomllib not available
                try:
                    content = (cwd / "pyproject.toml").read_text()
                    for line in content.split("\n"):
                        if line.startswith("name = "):
                            project_info["name"] = line.split('"')[1]
                            break
                except:
                    pass
        elif (cwd / "Cargo.toml").exists():
            project_info["type"] = "rust"
        elif (cwd / "go.mod").exists():
            project_info["type"] = "go"

        return project_info

    def _find_git_root(self, path: Path) -> Path | None:
        """Find the git repository root."""
        current = path
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        return None

    def _get_machine_info(self) -> dict[str, str]:
        """Get machine-specific information."""
        return {
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "machine": platform.machine(),
            "user": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
        }

    def _generate_instance_id(
        self, project_info: dict[str, Any], machine_info: dict[str, str]
    ) -> str:
        """Generate a unique instance ID based on project and machine."""
        # Create a hash of project path + hostname for consistency
        unique_string = f"{project_info['path']}:{machine_info['hostname']}"
        hash_obj = hashlib.sha256(unique_string.encode())
        # Use first 8 chars of hash for readability
        return hash_obj.hexdigest()[:8]

    def _generate_bot_name(
        self, project_info: dict[str, Any], machine_info: dict[str, str]
    ) -> str:
        """Generate a descriptive bot name."""
        project_name = project_info["name"].replace("/", "-").replace(" ", "-")
        hostname = machine_info["hostname"].split(".")[0]  # Remove domain

        # Create readable bot name
        if (
            project_info.get("git_branch")
            and project_info["git_branch"] != "main"
            and project_info["git_branch"] != "master"
        ):
            # Include branch if not main/master
            branch = project_info["git_branch"].replace("/", "-")
            return f"Claude-{project_name}-{branch}-{hostname}"
        else:
            return f"Claude-{project_name}-{hostname}"

    def _generate_stream_name(
        self, project_info: dict[str, Any], instance_id: str
    ) -> str:
        """Generate personal stream name - one stream for all Claude Code instances."""
        # Use a personal stream for the user (can be configured)
        user = self._get_machine_info()["user"]
        # Simple format: claude-code-{username} or just "claude-code" if shared
        return f"claude-code-{user}".lower()

    def _load_or_create_identity(self) -> dict[str, Any]:
        """Load existing identity or create new one."""
        project_info = self._get_project_info()
        machine_info = self._get_machine_info()
        instance_id = self._generate_instance_id(project_info, machine_info)

        # Check if we have an existing identity for this instance
        if self.identity_file.exists():
            try:
                with open(self.identity_file) as f:
                    identities = json.load(f)
                    if instance_id in identities:
                        # Update last_seen
                        identities[instance_id][
                            "last_seen"
                        ] = datetime.now().isoformat()
                        self._save_identities(identities)
                        return identities[instance_id]
            except:
                identities = {}
        else:
            identities = {}

        # Create new identity
        bot_name = self._generate_bot_name(project_info, machine_info)
        stream_name = self._generate_stream_name(project_info, instance_id)

        identity = {
            "instance_id": instance_id,
            "session_id": str(uuid.uuid4())[:8],  # Unique per session
            "bot_name": bot_name,
            "stream_name": stream_name,
            "project": project_info,
            "machine": machine_info,
            "created_at": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
        }

        # Save identity
        identities[instance_id] = identity
        self._save_identities(identities)

        return identity

    def _save_identities(self, identities: dict[str, Any]) -> None:
        """Save identities to file."""
        try:
            with open(self.identity_file, "w") as f:
                json.dump(identities, f, indent=2)
        except OSError:
            pass

    def get_instance_id(self) -> str:
        """Get the unique instance ID."""
        return self.identity["instance_id"]

    def get_session_id(self) -> str:
        """Get the current session ID."""
        return self.identity["session_id"]

    def get_bot_name(self) -> str:
        """Get the bot name for this instance."""
        return self.identity["bot_name"]

    def get_stream_name(self) -> str:
        """Get the stream name for this instance."""
        return self.identity["stream_name"]

    def get_topic_name(self) -> str:
        """Get the topic name for this project/instance."""
        project = self.identity["project"]["name"]
        branch = self.identity["project"].get("git_branch", "")
        hostname = self.identity["machine"]["hostname"].split(".")[0]

        # Format: "ProjectName (branch) - hostname"
        if branch and branch not in ["main", "master"]:
            return f"{project} ({branch}) - {hostname}"
        else:
            return f"{project} - {hostname}"

    def get_display_name(self) -> str:
        """Get a display name for notifications."""
        project = self.identity["project"]["name"]
        branch = self.identity["project"].get("git_branch", "")
        hostname = self.identity["machine"]["hostname"].split(".")[0]

        if branch and branch not in ["main", "master"]:
            return f"{project} ({branch}) on {hostname}"
        else:
            return f"{project} on {hostname}"

    def get_notification_prefix(self) -> str:
        """Get a prefix for notification messages."""
        return f"[{self.get_display_name()}]"

    def get_metadata(self) -> dict[str, Any]:
        """Get full metadata for this instance."""
        return {
            "instance_id": self.identity["instance_id"],
            "session_id": self.identity["session_id"],
            "bot_name": self.identity["bot_name"],
            "stream_name": self.identity["stream_name"],
            "project_name": self.identity["project"]["name"],
            "project_path": self.identity["project"]["path"],
            "project_type": self.identity["project"]["type"],
            "git_branch": self.identity["project"].get("git_branch"),
            "hostname": self.identity["machine"]["hostname"],
            "platform": self.identity["machine"]["platform"],
            "user": self.identity["machine"]["user"],
            "created_at": self.identity["created_at"],
            "last_seen": self.identity["last_seen"],
        }

    def list_all_instances(self) -> dict[str, Any]:
        """List all known instances."""
        if not self.identity_file.exists():
            return {}

        try:
            with open(self.identity_file) as f:
                return json.load(f)
        except:
            return {}

    def cleanup_old_instances(self, days: int = 30) -> int:
        """Remove instances not seen in specified days."""
        if not self.identity_file.exists():
            return 0

        try:
            with open(self.identity_file) as f:
                identities = json.load(f)

            cutoff = datetime.now().timestamp() - (days * 86400)
            removed = 0

            for instance_id in list(identities.keys()):
                last_seen = identities[instance_id].get("last_seen")
                if last_seen:
                    last_seen_ts = datetime.fromisoformat(last_seen).timestamp()
                    if last_seen_ts < cutoff:
                        del identities[instance_id]
                        removed += 1

            if removed > 0:
                self._save_identities(identities)

            return removed
        except:
            return 0


# Global instance
_instance_identity = None


def get_instance_identity() -> InstanceIdentity:
    """Get or create global instance identity."""
    global _instance_identity
    if _instance_identity is None:
        _instance_identity = InstanceIdentity()
    return _instance_identity
