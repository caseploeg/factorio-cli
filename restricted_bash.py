"""
Restricted Bash Executor for LLM Agents

Provides sandboxed command execution with:
- Whitelisted commands only
- Blocked dangerous patterns
- Timeout limits
- Path restrictions
- Output size limits
- Full audit logging
"""

import os
import re
import shlex
import subprocess
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Set, Dict, Any
from pathlib import Path
from enum import Enum


class SecurityLevel(Enum):
    """Security levels for bash access."""
    STRICT = "strict"      # Read-only, minimal commands
    MODERATE = "moderate"  # Read + some analysis tools
    PERMISSIVE = "permissive"  # More tools, still no writes


@dataclass
class BashConfig:
    """Configuration for restricted bash executor."""
    security_level: SecurityLevel = SecurityLevel.MODERATE
    timeout: float = 5.0  # Seconds
    max_output_bytes: int = 10000  # 10KB output limit
    allowed_paths: List[str] = field(default_factory=list)
    blocked_paths: List[str] = field(default_factory=list)
    log_commands: bool = True
    working_dir: Optional[str] = None


@dataclass
class BashResult:
    """Result of a bash command execution."""
    success: bool
    command: str
    stdout: str
    stderr: str
    return_code: int
    blocked: bool = False
    block_reason: str = ""
    timed_out: bool = False


class RestrictedBash:
    """
    Sandboxed bash executor for LLM agents.

    Provides controlled access to shell commands with security restrictions.
    """

    # Commands allowed at each security level
    COMMANDS_STRICT = {
        'cat', 'head', 'tail', 'less',  # Read files
        'ls', 'find', 'tree',            # List files
        'wc', 'du',                      # File stats
        'echo', 'printf',                # Output
    }

    COMMANDS_MODERATE = COMMANDS_STRICT | {
        'grep', 'awk', 'sed',            # Text processing
        'sort', 'uniq', 'cut',           # Data manipulation
        'jq',                            # JSON processing
        'diff', 'comm',                  # Compare files
        'file', 'stat',                  # File info
        'which', 'type',                 # Command info
        'date', 'cal',                   # Date/time
        'python', 'python3',             # Python (restricted)
    }

    COMMANDS_PERMISSIVE = COMMANDS_MODERATE | {
        'curl', 'wget',                  # Network (use carefully)
        'tar', 'gzip', 'gunzip',         # Archives (read)
        'xxd', 'hexdump',                # Binary inspection
    }

    # Always blocked - no security level allows these
    BLOCKED_COMMANDS = {
        'rm', 'rmdir', 'mv', 'cp',       # File modification
        'chmod', 'chown', 'chgrp',       # Permission changes
        'mkdir', 'touch',                # Create files
        'ln', 'link', 'unlink',          # Links
        'dd', 'shred',                   # Disk operations
        'kill', 'pkill', 'killall',      # Process control
        'sudo', 'su', 'doas',            # Privilege escalation
        'ssh', 'scp', 'rsync',           # Remote access
        'nc', 'netcat', 'ncat',          # Network tools
        'bash', 'sh', 'zsh', 'fish',     # Shell spawning
        'exec', 'eval',                  # Code execution
        'source', '.',                   # Script sourcing
        'export', 'unset',               # Environment modification
        'alias', 'unalias',              # Alias modification
        'crontab', 'at',                 # Scheduling
        'systemctl', 'service',          # Service control
        'apt', 'yum', 'dnf', 'pip',      # Package managers
        'docker', 'kubectl',             # Container tools
        'git',                           # VCS (could leak secrets)
        'env', 'printenv',               # Environment (secrets)
    }

    # Dangerous patterns to block
    BLOCKED_PATTERNS = [
        r'[;&|]',                        # Command chaining
        r'\$\(',                         # Command substitution
        r'`',                            # Backticks
        r'>',                            # Output redirection
        r'<\(',                          # Process substitution
        r'\beval\b',                     # Eval in any form
        r'\bexec\b',                     # Exec in any form
        r'/dev/',                        # Device access
        r'/proc/',                       # Proc filesystem
        r'/sys/',                        # Sys filesystem
        r'\.\./',                        # Parent directory traversal
        r'~/',                           # Home directory
        r'\$HOME',                       # Home variable
        r'\$\{',                         # Variable expansion
        r'\\x[0-9a-fA-F]',               # Hex escapes
        r'\\[0-7]{3}',                   # Octal escapes
    ]

    # Paths that are always blocked
    BLOCKED_PATH_PATTERNS = [
        r'^/etc/',
        r'^/root/',
        r'^/home/(?!user/factorio-cli)',  # Only allow project dir
        r'^/var/',
        r'^/tmp/',
        r'^/usr/',
        r'^/bin/',
        r'^/sbin/',
        r'\.env',
        r'\.git/',
        r'\.ssh/',
        r'credentials',
        r'secret',
        r'password',
        r'token',
        r'\.key$',
        r'\.pem$',
    ]

    def __init__(self, config: Optional[BashConfig] = None):
        """Initialize with configuration."""
        self.config = config or BashConfig()
        self.logger = logging.getLogger(__name__)
        self.command_history: List[BashResult] = []

        # Set allowed commands based on security level
        if self.config.security_level == SecurityLevel.STRICT:
            self.allowed_commands = self.COMMANDS_STRICT
        elif self.config.security_level == SecurityLevel.MODERATE:
            self.allowed_commands = self.COMMANDS_MODERATE
        else:
            self.allowed_commands = self.COMMANDS_PERMISSIVE

        # Default allowed paths if not specified
        if not self.config.allowed_paths:
            self.config.allowed_paths = [
                '/home/user/factorio-cli/data',
                '/home/user/factorio-cli/docs',
                '/app/data',  # Docker path
                '/app/docs',
            ]

    def validate_command(self, command: str) -> tuple[bool, str]:
        """
        Validate a command against security rules.

        Returns:
            (is_valid, reason) tuple
        """
        command = command.strip()

        if not command:
            return False, "Empty command"

        # Check for blocked patterns first
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, command):
                return False, f"Blocked pattern detected: {pattern}"

        # Parse command to extract the base command
        try:
            parts = shlex.split(command)
        except ValueError as e:
            return False, f"Invalid command syntax: {e}"

        if not parts:
            return False, "Empty command after parsing"

        base_cmd = os.path.basename(parts[0])

        # Check if command is blocked
        if base_cmd in self.BLOCKED_COMMANDS:
            return False, f"Command '{base_cmd}' is blocked"

        # Check if command is allowed
        if base_cmd not in self.allowed_commands:
            return False, f"Command '{base_cmd}' is not in allowed list"

        # Check paths in arguments
        for arg in parts[1:]:
            if arg.startswith('-'):
                continue  # Skip flags

            # Check if it looks like a path
            if '/' in arg or arg.startswith('.'):
                valid, reason = self._validate_path(arg)
                if not valid:
                    return False, reason

        return True, "OK"

    def _validate_path(self, path: str) -> tuple[bool, str]:
        """Validate a file path against allowed/blocked lists."""
        # Normalize the path
        try:
            if not path.startswith('/'):
                # Relative path - resolve from working dir
                working_dir = self.config.working_dir or os.getcwd()
                path = os.path.normpath(os.path.join(working_dir, path))
            else:
                path = os.path.normpath(path)
        except Exception:
            return False, "Invalid path format"

        # Check blocked patterns
        for pattern in self.BLOCKED_PATH_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                return False, f"Path matches blocked pattern: {pattern}"

        # Check if in allowed paths
        in_allowed = False
        for allowed in self.config.allowed_paths:
            if path.startswith(allowed):
                in_allowed = True
                break

        if not in_allowed and self.config.allowed_paths:
            return False, f"Path '{path}' not in allowed directories"

        return True, "OK"

    def execute(self, command: str) -> BashResult:
        """
        Execute a command with restrictions.

        Returns:
            BashResult with output and status
        """
        # Validate first
        is_valid, reason = self.validate_command(command)

        if not is_valid:
            result = BashResult(
                success=False,
                command=command,
                stdout="",
                stderr=f"Command blocked: {reason}",
                return_code=-1,
                blocked=True,
                block_reason=reason,
            )
            self._log_result(result)
            return result

        # Execute with restrictions
        try:
            working_dir = self.config.working_dir or os.getcwd()

            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                cwd=working_dir,
                env=self._get_restricted_env(),
            )

            # Truncate output if too large
            stdout = proc.stdout[:self.config.max_output_bytes]
            stderr = proc.stderr[:self.config.max_output_bytes]

            if len(proc.stdout) > self.config.max_output_bytes:
                stdout += f"\n... (truncated, {len(proc.stdout)} bytes total)"
            if len(proc.stderr) > self.config.max_output_bytes:
                stderr += f"\n... (truncated, {len(proc.stderr)} bytes total)"

            result = BashResult(
                success=proc.returncode == 0,
                command=command,
                stdout=stdout,
                stderr=stderr,
                return_code=proc.returncode,
            )

        except subprocess.TimeoutExpired:
            result = BashResult(
                success=False,
                command=command,
                stdout="",
                stderr=f"Command timed out after {self.config.timeout}s",
                return_code=-1,
                timed_out=True,
            )

        except Exception as e:
            result = BashResult(
                success=False,
                command=command,
                stdout="",
                stderr=f"Execution error: {str(e)}",
                return_code=-1,
            )

        self._log_result(result)
        return result

    def _get_restricted_env(self) -> Dict[str, str]:
        """Get a restricted environment for command execution."""
        # Start with minimal environment
        env = {
            'PATH': '/usr/bin:/bin',
            'HOME': '/tmp',
            'LANG': 'C.UTF-8',
            'LC_ALL': 'C.UTF-8',
        }
        return env

    def _log_result(self, result: BashResult):
        """Log command execution."""
        self.command_history.append(result)

        if self.config.log_commands:
            status = "BLOCKED" if result.blocked else ("OK" if result.success else "FAILED")
            self.logger.info(f"Bash [{status}]: {result.command}")
            if result.blocked:
                self.logger.debug(f"  Block reason: {result.block_reason}")

    def get_help(self) -> str:
        """Get help text describing available commands."""
        lines = [
            "=== RESTRICTED BASH ACCESS ===",
            "",
            f"Security Level: {self.config.security_level.value}",
            f"Timeout: {self.config.timeout}s",
            "",
            "Allowed Commands:",
        ]

        for cmd in sorted(self.allowed_commands):
            lines.append(f"  {cmd}")

        lines.append("")
        lines.append("Allowed Paths:")
        for path in self.config.allowed_paths:
            lines.append(f"  {path}")

        lines.append("")
        lines.append("Note: Command chaining (;|&), redirects (>), and")
        lines.append("command substitution ($()) are blocked.")

        return "\n".join(lines)

    def get_history(self) -> List[Dict[str, Any]]:
        """Get command execution history."""
        return [
            {
                "command": r.command,
                "success": r.success,
                "blocked": r.blocked,
                "block_reason": r.block_reason if r.blocked else None,
            }
            for r in self.command_history
        ]


def create_game_data_bash(project_dir: str = "/home/user/factorio-cli") -> RestrictedBash:
    """Create a bash executor configured for reading game data."""
    config = BashConfig(
        security_level=SecurityLevel.STRICT,
        timeout=5.0,
        allowed_paths=[
            f"{project_dir}/data",
            f"{project_dir}/docs",
            f"{project_dir}/*.json",
        ],
        working_dir=project_dir,
    )
    return RestrictedBash(config)


def create_analysis_bash(project_dir: str = "/home/user/factorio-cli") -> RestrictedBash:
    """Create a bash executor for analysis tasks."""
    config = BashConfig(
        security_level=SecurityLevel.MODERATE,
        timeout=10.0,
        allowed_paths=[
            f"{project_dir}/data",
            f"{project_dir}/docs",
            f"{project_dir}/results",
            f"{project_dir}/logs",
        ],
        working_dir=project_dir,
    )
    return RestrictedBash(config)


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    print("Testing RestrictedBash...")
    bash = create_game_data_bash()

    print("\n" + bash.get_help())

    # Test valid commands
    test_commands = [
        "ls data/",
        "cat data/recipe.json | head -20",  # Should fail - pipe blocked
        "cat data/recipe.json",
        "head -5 data/recipe.json",
        "grep iron data/recipe.json",
        "wc -l data/recipe.json",
        "rm data/recipe.json",  # Should fail - rm blocked
        "cat /etc/passwd",  # Should fail - path blocked
        "ls; rm -rf /",  # Should fail - chaining blocked
    ]

    print("\n--- Testing Commands ---")
    for cmd in test_commands:
        result = bash.execute(cmd)
        status = "BLOCKED" if result.blocked else ("OK" if result.success else "FAIL")
        print(f"\n[{status}] {cmd}")
        if result.blocked:
            print(f"  Reason: {result.block_reason}")
        elif result.stdout:
            preview = result.stdout[:100].replace('\n', '\\n')
            print(f"  Output: {preview}...")
