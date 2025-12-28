"""
GitHub Client for creating branches and PRs from Jules patches.

This module implements the 6-step process to:
1. Get base commit SHA
2. Create blobs for file contents
3. Create a tree
4. Create a commit
5. Create a branch reference
6. Create a pull request
"""
import os
import re
import httpx
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class GitHubClient:
    """Client for interacting with GitHub REST API to create branches and PRs."""
    
    def __init__(self, token: str = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN environment variable is required")
        
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    
    async def create_repository(
        self, 
        name: str, 
        description: str = "",
        private: bool = False,
        auto_init: bool = True
    ) -> Dict:
        """
        Create a new GitHub repository for the authenticated user.
        
        Args:
            name: Repository name
            description: Repository description
            private: Whether the repo is private
            auto_init: Whether to create an initial README
            
        Returns:
            Dict with repo info including 'full_name', 'html_url', 'clone_url'
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/user/repos",
                headers=self.headers,
                json={
                    "name": name,
                    "description": description,
                    "private": private,
                    "auto_init": auto_init
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def list_user_repos(self, per_page: int = 30) -> List[Dict]:
        """
        List repositories for the authenticated user.
        
        Returns:
            List of repo dicts with 'name', 'full_name', 'html_url', 'private'
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/user/repos",
                headers=self.headers,
                params={"per_page": per_page, "sort": "updated"}
            )
            response.raise_for_status()
            repos = response.json()
            return [{
                "name": r["name"],
                "full_name": r["full_name"],
                "html_url": r["html_url"],
                "private": r["private"],
                "description": r.get("description", ""),
                "owner": r["owner"]["login"]
            } for r in repos]
    
    async def delete_repository(self, owner: str, repo: str) -> bool:
        """
        Delete a GitHub repository.
        
        Note: Requires 'delete_repo' scope on the token.
        
        Returns:
            True if deleted successfully
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{self.base_url}/repos/{owner}/{repo}",
                headers=self.headers
            )
            # 204 No Content = success
            return response.status_code == 204
    
    async def list_branches(self, owner: str, repo: str) -> List[Dict]:
        """
        List all branches in a repository.
        
        Returns:
            List of branch dicts with 'name' and 'protected' fields
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/repos/{owner}/{repo}/branches",
                headers=self.headers,
                params={"per_page": 100}
            )
            response.raise_for_status()
            branches = response.json()
            return [{"name": b["name"], "protected": b.get("protected", False)} for b in branches]
    
    async def create_pr_from_patch(
        self,
        owner: str,
        repo: str,
        patch: str,
        commit_message: str,
        base_branch: str = "main",
        base_commit_id: str = None,
        branch_only: bool = False,
    ) -> Dict:
        """
        Create a new branch with the patch applied and optionally open a PR.
        
        Args:
            owner: GitHub repo owner
            repo: GitHub repo name
            patch: The unidiff patch string from Jules
            commit_message: The commit message
            base_branch: The branch to base the PR on (default: main)
            base_commit_id: Optional specific commit to base on
            branch_only: If True, only create branch without PR
            
        Returns:
            Dict with branch/PR URL and details
        """
        # Generate a unique branch name
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        branch_name = f"jules-patch-{timestamp}"
        
        # Parse the patch to get file changes
        file_changes = self._parse_patch(patch)
        
        if not file_changes:
            raise ValueError("No file changes found in patch")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Step 1: Get base commit SHA
            if base_commit_id:
                base_sha = base_commit_id
                # Get the tree SHA for this commit
                commit_resp = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/git/commits/{base_sha}",
                    headers=self.headers
                )
                commit_resp.raise_for_status()
                base_tree_sha = commit_resp.json()["tree"]["sha"]
            else:
                ref_resp = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/git/ref/heads/{base_branch}",
                    headers=self.headers
                )
                ref_resp.raise_for_status()
                base_sha = ref_resp.json()["object"]["sha"]
                
                # Get the tree SHA
                commit_resp = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/git/commits/{base_sha}",
                    headers=self.headers
                )
                commit_resp.raise_for_status()
                base_tree_sha = commit_resp.json()["tree"]["sha"]
            
            # Step 2 & 3: Create tree with file changes
            # For each file, we need to get current content and apply the patch
            tree_items = []
            
            for file_path, changes in file_changes.items():
                if changes["is_new"]:
                    # New file - just use the added content
                    new_content = "\n".join(changes["added_lines"])
                elif changes["is_deleted"]:
                    # Deleted file - set sha to null
                    tree_items.append({
                        "path": file_path,
                        "mode": "100644",
                        "type": "blob",
                        "sha": None
                    })
                    continue
                else:
                    # Modified file - get current content and apply patch
                    try:
                        content_resp = await client.get(
                            f"{self.base_url}/repos/{owner}/{repo}/contents/{file_path}",
                            headers=self.headers,
                            params={"ref": base_sha}
                        )
                        if content_resp.status_code == 200:
                            import base64
                            current_content = base64.b64decode(
                                content_resp.json()["content"]
                            ).decode("utf-8")
                            new_content = self._apply_patch_to_content(
                                current_content, changes
                            )
                        else:
                            # File doesn't exist, treat as new
                            new_content = "\n".join(changes["added_lines"])
                    except Exception as e:
                        print(f"Error fetching {file_path}: {e}")
                        new_content = "\n".join(changes["added_lines"])
                
                # Create blob for the new content
                blob_resp = await client.post(
                    f"{self.base_url}/repos/{owner}/{repo}/git/blobs",
                    headers=self.headers,
                    json={"content": new_content, "encoding": "utf-8"}
                )
                blob_resp.raise_for_status()
                blob_sha = blob_resp.json()["sha"]
                
                tree_items.append({
                    "path": file_path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha
                })
            
            # Create the tree
            tree_resp = await client.post(
                f"{self.base_url}/repos/{owner}/{repo}/git/trees",
                headers=self.headers,
                json={"base_tree": base_tree_sha, "tree": tree_items}
            )
            tree_resp.raise_for_status()
            new_tree_sha = tree_resp.json()["sha"]
            
            # Step 4: Create commit
            # Parse commit message into title and body
            lines = commit_message.strip().split("\n", 1)
            title = lines[0]
            body = lines[1].strip() if len(lines) > 1 else ""
            
            commit_resp = await client.post(
                f"{self.base_url}/repos/{owner}/{repo}/git/commits",
                headers=self.headers,
                json={
                    "message": commit_message,
                    "tree": new_tree_sha,
                    "parents": [base_sha]
                }
            )
            commit_resp.raise_for_status()
            new_commit_sha = commit_resp.json()["sha"]
            
            # Step 5: Create branch reference
            ref_resp = await client.post(
                f"{self.base_url}/repos/{owner}/{repo}/git/refs",
                headers=self.headers,
                json={
                    "ref": f"refs/heads/{branch_name}",
                    "sha": new_commit_sha
                }
            )
            ref_resp.raise_for_status()
            
            branch_url = f"https://github.com/{owner}/{repo}/tree/{branch_name}"
            
            # Step 6: Create pull request (optional)
            if branch_only:
                return {
                    "success": True,
                    "branch": branch_name,
                    "branch_url": branch_url,
                    "title": title,
                    "type": "branch"
                }
            
            pr_resp = await client.post(
                f"{self.base_url}/repos/{owner}/{repo}/pulls",
                headers=self.headers,
                json={
                    "title": title,
                    "head": branch_name,
                    "base": base_branch,
                    "body": body or "Created by Jules via Mobile App"
                }
            )
            pr_resp.raise_for_status()
            pr_data = pr_resp.json()
            
            return {
                "success": True,
                "pr_number": pr_data["number"],
                "pr_url": pr_data["html_url"],
                "branch": branch_name,
                "title": title,
                "type": "pr"
            }
    
    def _parse_patch(self, patch: str) -> Dict[str, Dict]:
        """
        Parse a unidiff patch string into file changes.
        
        Returns:
            Dict mapping file paths to their changes
        """
        file_changes = {}
        current_file = None
        
        lines = patch.split("\n")
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Match file header: +++ b/path/to/file
            if line.startswith("+++ b/"):
                current_file = line[6:]  # Remove "+++ b/"
                file_changes[current_file] = {
                    "is_new": False,
                    "is_deleted": False,
                    "added_lines": [],
                    "removed_lines": [],
                    "hunks": []
                }
            elif line.startswith("--- a/"):
                prev_file = line[6:]
                # Check if next line shows /dev/null (new file)
                if i + 1 < len(lines) and "+++ b/" in lines[i + 1]:
                    pass  # Normal modification
            elif line.startswith("--- /dev/null"):
                # New file
                if current_file:
                    file_changes[current_file]["is_new"] = True
            elif line.startswith("+++ /dev/null"):
                # Deleted file
                if current_file:
                    file_changes[current_file]["is_deleted"] = True
            elif line.startswith("@@"):
                # Hunk header: @@ -start,count +start,count @@
                match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
                if match and current_file:
                    file_changes[current_file]["hunks"].append({
                        "old_start": int(match.group(1)),
                        "old_count": int(match.group(2) or 1),
                        "new_start": int(match.group(3)),
                        "new_count": int(match.group(4) or 1),
                        "lines": []
                    })
            elif current_file and file_changes[current_file]["hunks"]:
                # Content line within a hunk
                current_hunk = file_changes[current_file]["hunks"][-1]
                if line.startswith("+") and not line.startswith("+++"):
                    current_hunk["lines"].append(("add", line[1:]))
                    file_changes[current_file]["added_lines"].append(line[1:])
                elif line.startswith("-") and not line.startswith("---"):
                    current_hunk["lines"].append(("remove", line[1:]))
                    file_changes[current_file]["removed_lines"].append(line[1:])
                elif line.startswith(" "):
                    current_hunk["lines"].append(("context", line[1:]))
            
            i += 1
        
        return file_changes
    
    def _apply_patch_to_content(self, original: str, changes: Dict) -> str:
        """
        Apply patch changes to original file content.
        
        This is a simplified implementation that works for most cases.
        For complex patches, consider using a proper diff library.
        """
        if not changes["hunks"]:
            # No hunks, just return added lines
            return "\n".join(changes["added_lines"])
        
        original_lines = original.split("\n")
        result_lines = []
        original_idx = 0
        
        for hunk in changes["hunks"]:
            # Copy lines before the hunk
            target_line = hunk["old_start"] - 1  # 0-indexed
            while original_idx < target_line and original_idx < len(original_lines):
                result_lines.append(original_lines[original_idx])
                original_idx += 1
            
            # Apply hunk changes
            for action, line_content in hunk["lines"]:
                if action == "context":
                    result_lines.append(line_content)
                    original_idx += 1
                elif action == "add":
                    result_lines.append(line_content)
                elif action == "remove":
                    original_idx += 1  # Skip the removed line
        
        # Copy remaining lines after last hunk
        while original_idx < len(original_lines):
            result_lines.append(original_lines[original_idx])
            original_idx += 1
        
        return "\n".join(result_lines)


# Factory function to get client (returns None if no token)
def get_github_client() -> Optional[GitHubClient]:
    """Get a GitHubClient instance if GITHUB_TOKEN is set."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return None
    return GitHubClient(token)
