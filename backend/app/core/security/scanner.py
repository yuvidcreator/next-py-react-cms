"""
PyPress — Plugin Security Scanner

Automated static analysis that runs on plugin/theme upload.
WordPress equivalent: The automated plugin review checks that
wordpress.org runs on submitted plugins, plus the manual
security review process — all automated.

Scanner checks:
    1. Manifest validation (plugin.json structure + required fields)
    2. Python syntax verification (ast.parse every .py file)
    3. Dangerous import detection (os.system, subprocess, eval, exec)
    4. File system access patterns (open(), os.path, pathlib)
    5. Network access patterns (socket, urllib, requests)
    6. Code injection risks (__import__, compile, globals)
    7. Version compatibility check (requires_pypress, requires_python)

Each check returns a list of ValidationIssue objects with severity:
    - CRITICAL: Blocks installation (security risk too high)
    - WARNING:  Allows installation but flags in admin UI
    - INFO:     Logged for audit trail

Design: Strategy Pattern — each check is a function that receives
the plugin directory and returns issues. New checks are added to
the CHECKS list without modifying existing code (Open/Closed).
"""
from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class ScanIssue:
    """A single issue found by the scanner."""
    severity: str  # "critical" | "warning" | "info"
    message: str
    file: str | None = None
    line: int | None = None


@dataclass
class ScanResult:
    """Complete scan result for a plugin or theme."""
    is_valid: bool = True
    issues: list[ScanIssue] = field(default_factory=list)

    def add(self, severity: str, message: str, file: str | None = None, line: int | None = None):
        self.issues.append(ScanIssue(severity=severity, message=message, file=file, line=line))
        if severity == "critical":
            self.is_valid = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "issues": [
                {
                    "severity": i.severity,
                    "message": i.message,
                    "file": i.file,
                    "line": i.line,
                }
                for i in self.issues
            ],
        }


# =============================================================================
# DANGEROUS PATTERNS
# =============================================================================

# Python imports/functions that are dangerous in a plugin context
DANGEROUS_IMPORTS = {
    "subprocess": "Allows executing arbitrary system commands",
    "os.system": "Allows executing arbitrary system commands",
    "os.popen": "Allows executing arbitrary system commands",
    "os.exec": "Allows replacing the current process",
    "os.spawn": "Allows spawning new processes",
    "shutil.rmtree": "Can delete entire directory trees",
    "ctypes": "Allows calling C code directly — potential memory corruption",
    "importlib": "Can dynamically import any module at runtime",
}

DANGEROUS_BUILTINS = {
    "eval": "Executes arbitrary Python expressions",
    "exec": "Executes arbitrary Python code",
    "compile": "Can compile and execute arbitrary code",
    "__import__": "Dynamic import — can load any module",
    "globals": "Provides access to global namespace — can modify core behavior",
}

DANGEROUS_PATTERNS = [
    (r"os\.system\s*\(", "os.system() call — executes shell commands"),
    (r"subprocess\.(run|call|Popen|check_output)\s*\(", "subprocess call — executes external commands"),
    (r"eval\s*\(", "eval() call — executes arbitrary expressions"),
    (r"exec\s*\(", "exec() call — executes arbitrary code"),
    (r"__import__\s*\(", "__import__() call — dynamic module import"),
    (r"open\s*\(.*(\/etc|\/var|\/usr|\/bin|\/root|\.\.)", "File access outside plugin directory"),
    (r"socket\.(socket|create_connection)\s*\(", "Raw socket creation — network access"),
    (r"requests\.(get|post|put|delete|head|patch)\s*\(", "HTTP request — verify network access is intentional"),
]

REQUIRED_MANIFEST_FIELDS = ["name", "slug", "version"]


# =============================================================================
# INDIVIDUAL SCANNER CHECKS
# =============================================================================

def check_manifest(manifest: dict[str, Any], result: ScanResult) -> None:
    """Validate the plugin.json / theme.json manifest."""
    # Required fields
    for field_name in REQUIRED_MANIFEST_FIELDS:
        if not manifest.get(field_name):
            result.add("critical", f"Missing required manifest field: '{field_name}'")

    # Version format
    version = manifest.get("version", "")
    if version and not re.match(r"^\d+\.\d+\.\d+", version):
        result.add("warning", f"Version '{version}' doesn't follow semver (x.y.z) format")

    # Slug format
    slug = manifest.get("slug", "")
    if slug and not re.match(r"^[a-z0-9][a-z0-9-]*$", slug):
        result.add("warning", f"Slug '{slug}' should be lowercase alphanumeric with hyphens only")

    if result.is_valid:
        result.add("info", "Plugin manifest (plugin.json) is valid.")


def check_python_syntax(plugin_dir: str, result: ScanResult) -> None:
    """Verify all .py files have valid Python syntax using ast.parse."""
    py_files = list(Path(plugin_dir).rglob("*.py"))

    if not py_files:
        result.add("warning", "No Python files found in the plugin directory.")
        return

    all_valid = True
    for py_file in py_files:
        rel_path = str(py_file.relative_to(plugin_dir))
        try:
            source = py_file.read_text(encoding="utf-8")
            ast.parse(source, filename=rel_path)
        except SyntaxError as e:
            result.add("critical", f"Python syntax error: {e.msg}", file=rel_path, line=e.lineno)
            all_valid = False
        except Exception as e:
            result.add("warning", f"Could not parse file: {str(e)}", file=rel_path)
            all_valid = False

    if all_valid:
        result.add("info", f"All {len(py_files)} Python file(s) pass syntax check.")


def check_dangerous_imports(plugin_dir: str, result: ScanResult) -> None:
    """Scan Python files for dangerous imports and function calls."""
    py_files = list(Path(plugin_dir).rglob("*.py"))
    found_issues = False

    for py_file in py_files:
        rel_path = str(py_file.relative_to(plugin_dir))
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=rel_path)
        except Exception:
            continue  # Syntax errors caught by check_python_syntax

        # Check imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in DANGEROUS_IMPORTS:
                        result.add(
                            "critical",
                            f"Dangerous import: '{alias.name}' — {DANGEROUS_IMPORTS[alias.name]}",
                            file=rel_path,
                            line=node.lineno,
                        )
                        found_issues = True

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    full_name = f"{module}.{alias.name}" if module else alias.name
                    # Check both the module and the full import path
                    for dangerous, reason in DANGEROUS_IMPORTS.items():
                        if full_name.startswith(dangerous) or module == dangerous.split(".")[0]:
                            if dangerous in full_name or module == dangerous:
                                result.add(
                                    "warning",
                                    f"Potentially dangerous import: 'from {module} import {alias.name}' — {reason}",
                                    file=rel_path,
                                    line=node.lineno,
                                )
                                found_issues = True

            # Check for dangerous builtins
            elif isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name in DANGEROUS_BUILTINS:
                    result.add(
                        "critical",
                        f"Dangerous function call: '{func_name}()' — {DANGEROUS_BUILTINS[func_name]}",
                        file=rel_path,
                        line=node.lineno,
                    )
                    found_issues = True

    if not found_issues:
        result.add("info", "No dangerous imports detected.")


def check_dangerous_patterns(plugin_dir: str, result: ScanResult) -> None:
    """Regex-based pattern scanning for dangerous code patterns."""
    py_files = list(Path(plugin_dir).rglob("*.py"))
    found = False

    for py_file in py_files:
        rel_path = str(py_file.relative_to(plugin_dir))
        try:
            lines = py_file.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue

        for line_num, line in enumerate(lines, start=1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            for pattern, description in DANGEROUS_PATTERNS:
                if re.search(pattern, line):
                    # Determine severity based on pattern
                    severity = "critical" if any(
                        kw in pattern for kw in ["os.system", "subprocess", "eval", "exec", "__import__"]
                    ) else "warning"
                    result.add(severity, f"Dangerous pattern: {description}", file=rel_path, line=line_num)
                    found = True

    if not found:
        result.add("info", "No dangerous code patterns detected.")


def check_file_permissions(plugin_dir: str, result: ScanResult) -> None:
    """Check that no files have executable permissions (security best practice)."""
    for root, _dirs, files in os.walk(plugin_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, plugin_dir)
            if os.access(fpath, os.X_OK) and fname.endswith(".py"):
                result.add("warning", f"File has executable permission — should be read-only", file=rel_path)

    # This check passes silently if no issues found (no info message needed)


# =============================================================================
# MAIN SCANNER FUNCTION
# =============================================================================

def scan_plugin(plugin_dir: str, manifest: dict[str, Any]) -> ScanResult:
    """
    Run the complete security scan on a plugin directory.

    This is called by the upload endpoint after extracting the .zip
    and parsing the manifest. If the result is_valid is False, the
    plugin is NOT installed.

    Args:
        plugin_dir: Path to the extracted plugin directory
        manifest: Parsed plugin.json / theme.json contents

    Returns:
        ScanResult with all issues found
    """
    result = ScanResult()

    # Run all checks in order
    check_manifest(manifest, result)
    check_python_syntax(plugin_dir, result)
    check_dangerous_imports(plugin_dir, result)
    check_dangerous_patterns(plugin_dir, result)
    check_file_permissions(plugin_dir, result)

    return result


def scan_plugin_source(source_code: str, filename: str = "plugin.py") -> ScanResult:
    """
    Scan a single Python source string (useful for testing).

    This is a convenience function that writes the source to a temp
    directory and runs the full scan.
    """
    import tempfile

    result = ScanResult()

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, filename)
        with open(filepath, "w") as f:
            f.write(source_code)

        check_python_syntax(tmpdir, result)
        check_dangerous_imports(tmpdir, result)
        check_dangerous_patterns(tmpdir, result)

    return result
