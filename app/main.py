import os
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from agents import Agent, Runner, function_tool

from app.repo_tools import get_repo_tree, read_file, search_repo

load_dotenv()
console = Console()

REPO_PATH = os.environ.get("REPO_PATH", "").strip()
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


agent = Agent(
    name="DQMC_repo_tutor",
    model="gpt-4.1-mini",
    instructions=(
        "You are an expert code-reading assistant for computational physics repositories. "
        "Your job is to help the user understand code structure, algorithmic intent, "
        "and likely physical meaning. "
        "Always ground your answers in the repo tools first. "
        "If the user asks about a file or function, inspect the repo before answering. "
        "When discussing physical meaning, clearly separate: "
        "(1) what is directly supported by code evidence, "
        "(2) what is an inference from standard computational physics practice. "
        "If asked to create a new data-processing script, first inspect relevant existing files "
        "and outputs, then draft a script that matches the repo style."
    ),
    tools=[repo_tree, repo_read, repo_search],
)

def main():
    console.print(Panel.fit(
        "Physics Repo Tutor\n"
        "Examples:\n"
        "  - Summarize this repository\n"
        "  - What does src/dqmc.py do?\n"
        "  - Search for Green function measurement\n"
        "  - Create a new script to postprocess conductivity output",
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