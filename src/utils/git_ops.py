"""Git operations wrapper."""
import git
import os
import sys
from typing import Optional
from git import RemoteProgress


class CloneProgress(RemoteProgress):
    def __init__(self, callback=None):
        super().__init__()
        self.callback = callback

    def update(self, op_code, cur_count, max_count=None, message=''):
        if self.callback and max_count:
            pct = int(cur_count / max_count * 100)
            self.callback(pct, message)

# Configure GitPython to hide console windows on Windows
if sys.platform == "win32":
    # GitPython uses subprocess internally; this prevents console windows
    os.environ["GIT_TERMINAL_PROMPT"] = "0"

# Clear environment variables that can override GitPython's repo detection.
# On some machines GIT_DIR / GIT_WORK_TREE may be set globally, causing
# operations to target the wrong directory (e.g. the portable git folder).
for _var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_CEILING_DIRECTORIES"):
    os.environ.pop(_var, None)


def clone_repo(url: str, dest: str, branch: str = "master",
               commit: Optional[str] = None,
               progress_callback=None) -> git.Repo:
    """Clone a git repository. Optionally checkout a specific commit."""
    progress = CloneProgress(progress_callback) if progress_callback else None
    repo = git.Repo.clone_from(url, dest, branch=branch, progress=progress)
    if commit:
        repo.git.checkout(commit)
    return repo


def get_current_commit(repo_path: str, short: bool = False) -> str:
    """Get current HEAD commit hash."""
    repo = git.Repo(repo_path)
    hexsha = repo.head.commit.hexsha
    return hexsha[:7] if short else hexsha


def get_branches(repo_path: str) -> list:
    """List remote branches."""
    repo = git.Repo(repo_path)
    return [ref.remote_head for ref in repo.remotes.origin.refs]


def list_branches_with_dates(repo_path: str) -> list:
    """Return remote branches with last-commit date, sorted by date desc.

    Each entry: {"name": str, "date": ISO-8601 str}.
    """
    repo = git.Repo(repo_path)
    out = []
    for ref in repo.remotes.origin.refs:
        name = ref.remote_head
        if name == "HEAD":
            continue
        try:
            dt = ref.commit.committed_datetime.isoformat()
        except Exception:
            dt = ""
        out.append({"name": name, "date": dt})
    out.sort(key=lambda b: b["date"] or "", reverse=True)
    return out


def get_log(repo_path: str, count: int = 20) -> list:
    """Get recent commit log entries."""
    repo = git.Repo(repo_path)
    commits = []
    for c in repo.iter_commits(max_count=count):
        commits.append({
            "hash": c.hexsha,
            "message": c.message.strip(),
            "author": c.author.name,
            "date": c.committed_datetime.isoformat(),
        })
    return commits


def checkout(repo_path: str, ref: str) -> None:
    """Checkout a specific ref (branch, tag, or commit)."""
    repo = git.Repo(repo_path)
    repo.git.checkout(ref)


def pull(repo_path: str) -> None:
    """Pull latest changes from origin."""
    repo = git.Repo(repo_path)
    repo.remotes.origin.pull()


def get_remote_head_for_current_branch(repo_path: str) -> Optional[str]:
    """Best-effort remote HEAD commit for the current branch.

    Returns full commit hash string, or None when it cannot be resolved.
    """
    try:
        repo = git.Repo(repo_path)
    except Exception:
        return None

    def _extract_ref_hash(output: str, expected_ref: str) -> Optional[str]:
        """Return hash for exact ref match from ls-remote output."""
        for raw_line in (output or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == expected_ref:
                return parts[0]
        return None

    try:
        if not repo.head.is_detached:
            branch = repo.active_branch.name
            # Query exact ref to avoid partial matches like refs/heads/*/main.
            expected_ref = f"refs/heads/{branch}"
            output = repo.git.ls_remote("--heads", "origin", expected_ref)
            branch_head = _extract_ref_hash(output, expected_ref)
            if branch_head:
                return branch_head

        output = repo.git.ls_remote("origin", "HEAD")
        if output and output.strip():
            return output.strip().split()[0]
    except Exception:
        return None

    return None


def has_remote_updates(repo_path: str) -> Optional[bool]:
    """Return True if remote branch head differs from local HEAD.

    Returns:
        True/False when check succeeds, or None when status is unknown.
    """
    try:
        local = get_current_commit(repo_path)
        remote = get_remote_head_for_current_branch(repo_path)
    except Exception:
        return None

    if not remote:
        return None
    return local != remote


def list_remote_tags(url: str) -> list:
    """Fetch tags from remote repo via ls-remote. Returns list of dicts [{name, hash}].
    Sorted by version number descending (newest first). Falls back to alphabetical if not semver."""
    g = git.cmd.Git()
    output = g.ls_remote("--tags", url)
    tags = []
    deref_map = {}  # tag name -> dereferenced commit hash
    for line in output.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        hexsha = parts[0]
        ref = parts[1]
        if ref.endswith("^{}"):
            # Dereferenced commit hash for annotated tags — prefer this
            name = ref.replace("refs/tags/", "").rstrip("^{}")
            deref_map[name] = hexsha
        else:
            name = ref.replace("refs/tags/", "")
            tags.append({"name": name, "hash": hexsha})
    # Use dereferenced commit hash when available (annotated tags)
    for tag in tags:
        if tag["name"] in deref_map:
            tag["hash"] = deref_map[tag["name"]]
    # Try to sort by semantic version descending
    from packaging.version import Version, InvalidVersion
    def sort_key(tag):
        try:
            return (1, Version(tag["name"].lstrip("v")))
        except InvalidVersion:
            return (0, tag["name"])
    tags.sort(key=sort_key, reverse=True)
    return tags


def list_tags_with_dates(repo_path: str) -> list:
    """List tags with commit dates from a local repo.
    Returns [{name, date}] sorted by semver descending.
    Date format: YYYY-MM-DD."""
    repo = git.Repo(repo_path)
    tags = []
    for tag in repo.tags:
        try:
            committed_dt = tag.commit.committed_datetime
        except Exception:
            continue
        tags.append({
            "name": tag.name,
            "date": committed_dt.strftime("%Y-%m-%d"),
            "hash": tag.commit.hexsha,
        })
    from packaging.version import Version, InvalidVersion
    def sort_key(tag):
        try:
            return (1, Version(tag["name"].lstrip("v")))
        except InvalidVersion:
            return (0, tag["name"])
    tags.sort(key=sort_key, reverse=True)
    return tags


def list_remote_branches(url: str) -> list:
    """Fetch branch names from remote repo via ls-remote. Returns list of branch name strings."""
    g = git.cmd.Git()
    output = g.ls_remote("--heads", url)
    branches = []
    for line in output.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        ref = parts[1]
        name = ref.replace("refs/heads/", "")
        branches.append(name)
    branches.sort()
    return branches


def list_tags(repo_path: str) -> list:
    """List tags in a local repo. Returns list of dicts [{name, hash}]."""
    repo = git.Repo(repo_path)
    tags = []
    for tag in repo.tags:
        tags.append({
            "name": tag.name,
            "hash": tag.commit.hexsha[:7],
        })
    from packaging.version import Version, InvalidVersion
    def sort_key(tag):
        try:
            return (1, Version(tag["name"].lstrip("v")))
        except InvalidVersion:
            return (0, tag["name"])
    tags.sort(key=sort_key, reverse=True)
    return tags
