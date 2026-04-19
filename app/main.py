import os
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from agents import Agent, Runner, function_tool

from app.repo_tools import (
    get_repo_tree,
    read_file,
    search_repo,
    write_agent_file,
    check_python_file,
)
from app.retrieval import format_candidates_for_agent

load_dotenv()
console = Console()

REPO_PATH = os.environ.get("REPO_PATH", "").strip()
INDEX_PATH = os.environ.get("INDEX_PATH", "data/repo_index.jsonl").strip()

if not REPO_PATH:
    raise RuntimeError("REPO_PATH is not set in .env")


@function_tool
def repo_tree() -> str:
    """Return a tree-like summary of the repository structure."""
    return get_repo_tree(REPO_PATH)


@function_tool
def repo_read(relative_path: str) -> str:
    """Read a text file from the repository by relative path."""
    return read_file(REPO_PATH, relative_path)


@function_tool
def repo_search(query: str) -> str:
    """Search for a string in the repository and return matching snippets."""
    hits = search_repo(REPO_PATH, query)
    if not hits:
        return "No matches found."

    chunks = []
    for i, hit in enumerate(hits, 1):
        chunks.append(
            f"[{i}] {hit['path']}\n{hit['snippet']}\n{'-'*60}"
        )
    return "\n".join(chunks)


@function_tool
def repo_index_search(query: str) -> str:
    """Search the offline repository index and return the most relevant files first."""
    return format_candidates_for_agent(query, INDEX_PATH, top_k=8)


@function_tool
def write_file(relative_path: str, content: str) -> str:
    """Write generated content to a file under agent_outputs/ inside the repo."""
    return write_agent_file(REPO_PATH, relative_path, content)


@function_tool
def check_python(relative_path: str) -> str:
    """Run Python syntax check on a file under the repository."""
    return check_python_file(REPO_PATH, relative_path)


agent = Agent(
    name="physics_repo_builder",
    model="gpt-5-mini",
    instructions=(
        "You are an expert assistant for computational physics repositories. "
        "You help users understand source code, identify physical meaning when supported by code evidence, "
        "and create new postprocessing scripts aligned with repository conventions.\n\n"

        "Workflow rules:\n"
        "1. For any nontrivial repo question, first call repo_index_search.\n"
        "2. Then inspect the most relevant files using repo_read.\n"
        "3. Use repo_search when you need symbol-level or phrase-level confirmation.\n"
        "4. Separate clearly:\n"
        "   - direct code evidence\n"
        "   - inference from standard computational physics practice\n"
        "5. When asked to create a new script:\n"
        "   - inspect similar existing files first\n"
        "   - infer file naming and I/O patterns\n"
        "   - write the new script under agent_outputs/\n"
        "   - then run check_python on it\n"
        "   - report the final saved path and syntax-check result\n"
        "6. Do not modify core repo files. Only write under agent_outputs/.\n"
        "7. If repository evidence is incomplete, say so explicitly."
    ),
    tools=[
        repo_tree,
        repo_read,
        repo_search,
        repo_index_search,
        write_file,
        check_python,
    ],
)

def main():
    console.print(Panel.fit(
        "Physics Repo Builder\n"
        "Recommended tests:\n"
        "  - Summarize the core data flow of this repository\n"
        "  - Find files related to Green function measurement\n"
        "  - Create a new postprocess script for density vs temperature and save it under agent_outputs/",
        title="Agent Ready"
    ))

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit"}:
            break

        result = Runner.run_sync(agent, user_input)
        console.print("\n[bold cyan]Agent:[/bold cyan]")
        console.print(result.final_output)


if __name__ == "__main__":
    main()