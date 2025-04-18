import os
import subprocess
from pathlib import Path

# Define project root as the directory containing this file
project_root = Path(__file__).resolve().parent

# Security helper


def _is_safe_path(path_str: str) -> bool:
    try:
        target_path = (project_root / path_str).resolve()
        return target_path.is_relative_to(project_root)
    except Exception:
        return False


def read_file(path: str) -> str:
    """Reads the content of a file at the given relative path."""
    if not _is_safe_path(path):
        return f"Error: Access denied: Path '{path}' is outside the allowed directory."
    file_path = (project_root / path).resolve()
    if not file_path.is_file():
        return f"Error: Path '{path}' is not a file or does not exist."
    try:
        return file_path.read_text(encoding='utf-8')
    except Exception as e:
        return f"Error reading file '{path}': {e}"


def list_files(directory: str = '.') -> str:
    """Lists files and directories within a given relative path."""
    if not _is_safe_path(directory):
        return f"Error: Access denied: Path '{directory}' is outside the allowed directory."
    dir_path = (project_root / directory).resolve()
    if not dir_path.is_dir():
        return f"Error: Path '{directory}' is not a directory."
    try:
        items = [f.name + ('/' if f.is_dir() else '')
                 for f in dir_path.iterdir()]
        return f"Contents of '{directory}':\n" + "\n".join(items)
    except Exception as e:
        return f"Error listing directory '{directory}': {e}"


def edit_file(path: str, content: str) -> str:
    """Writes content to a file at the given relative path, overwriting it."""
    if not _is_safe_path(path):
        return f"Error: Access denied: Path '{path}' is outside the allowed directory."
    file_path = (project_root / path).resolve()
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        return f"Successfully wrote to '{path}'."
    except Exception as e:
        return f"Error writing to file '{path}': {e}"


def execute_bash_command(command: str) -> str:
    """Executes a whitelisted bash command in the project's root directory."""
    whitelist = ["ls", "cat", "git add",
                 "git status", "git commit", "git push"]
    is_whitelisted = any(command.strip().startswith(prefix)
                         for prefix in whitelist)
    if not is_whitelisted:
        return f"Error: Command '{command}' is not allowed. Only specific commands (ls, cat, git add/status/commit/push) are permitted."
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=project_root,
            check=False
        )
        output = f"- stdout -\n{result.stdout}\n- stderr -\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n- Command exited with code: {result.returncode} -"
        return output.strip()
    except Exception as e:
        return f"Error executing command '{command}': {e}"


def run_in_sandbox(command: str, image: str = "python:3.11-slim") -> str:
    """Executes a command inside a sandboxed Docker container."""
    try:
        import docker
        from docker.errors import DockerException
    except ImportError:
        return "Error: docker Python package is not installed."
    try:
        client = docker.from_env()
        client.ping()
    except DockerException as e:
        return f"Error: Docker connection failed: {e}\nPlease ensure Docker is running."
    except Exception as e:
        return f"Error: Could not connect to Docker: {e}"
    try:
        container_output = client.containers.run(
            image=image,
            command=f"sh -c '{command}'",
            working_dir="/app",
            volumes={str(project_root): {'bind': '/app', 'mode': 'rw'}},
            remove=True,
            network_mode='none',
            mem_limit='512m',
            cpus=1,
            detach=False,
            stdout=True,
            stderr=True
        )
        output_str = container_output.decode('utf-8').strip()
        return f"- Container Output -\n{output_str}"
    except DockerException as e:
        error_msg = f"Docker error during sandbox execution: {e}"
        if "not found" in str(e).lower() or "no such image" in str(e).lower():
            error_msg += f"\nPlease ensure the image '{image}' exists locally or can be pulled."
        return f"Error: {error_msg}"
    except Exception as e:
        return f"Error: Unexpected error during sandbox execution: {e}"
