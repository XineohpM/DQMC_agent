import os
from dotenv import load_dotenv
from agents import Agent, function_tool
from app.io_tools import format_io_hits

from app.repo_tools import (
    get_repo_tree,
    read_file,
    search_repo,
    write_agent_file,
    check_python_file,
)
from app.retrieval import format_candidates_for_agent
from app.semantic_tools import format_semantic_hits, format_glossary_hits

load_dotenv()

REPO_PATH = os.environ.get("REPO_PATH", "").strip()
INDEX_PATH = os.environ.get("INDEX_PATH", "data/repo_index.jsonl").strip()
IO_INDEX_PATH = os.environ.get("IO_INDEX_PATH", "data/io_index.jsonl").strip()
SEMANTIC_PATH = os.environ.get("SEMANTIC_PATH", "data/semantic_map.jsonl").strip()
GLOSSARY_PATH = os.environ.get("GLOSSARY_PATH", "data/theory_glossary.jsonl").strip()

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
        chunks.append(f"[{i}] {hit['path']}\n{hit['snippet']}\n{'-'*60}")
    return "\n".join(chunks)


@function_tool
def repo_index_search(query: str) -> str:
    """Search the offline repository index and return the most relevant files first."""
    return format_candidates_for_agent(query, INDEX_PATH, top_k=8)


@function_tool
def io_search(query: str) -> str:
    """Search the repository I/O index for HDF5 keys, parameter usage, read/write patterns, and file roles."""
    return format_io_hits(query, IO_INDEX_PATH, top_k=10)


@function_tool
def semantic_search(query: str) -> str:
    """Search the project semantic map for code-object to physics-concept mappings."""
    return format_semantic_hits(query, SEMANTIC_PATH, top_k=8)


@function_tool
def theory_search(query: str) -> str:
    """Search the small theory glossary for background concept definitions."""
    return format_glossary_hits(query, GLOSSARY_PATH, top_k=6)


@function_tool
def write_file(relative_path: str, content: str) -> str:
    """Write generated content to a file under agent_outputs/ inside the repo."""
    return write_agent_file(REPO_PATH, relative_path, content)


@function_tool
def check_python(relative_path: str) -> str:
    """Run Python syntax check on a file under the repository."""
    return check_python_file(REPO_PATH, relative_path)



def build_agent() -> Agent:
    '''Build the agent.'''
    agent = Agent(
        name="DQMC_repo_agent",
        model="gpt-5-mini",
        instructions=(
            "You are an expert assistant for computational physics repositories.\n\n"

            "Your tasks are:\n"
            "1. Help the user understand source code and data flow.\n"
            "2. Explain the likely physical meaning of code objects, while clearly separating code evidence from interpretation.\n"
            "3. Create new postprocessing scripts aligned with repository conventions.\n\n"

            "Required workflow rules:\n"
            "A. For any nontrivial repository question, first call repo_index_search.\n"
            "B. For questions about physical meaning, observables, correlators, or parameters, also call semantic_search.\n"
            "C. For questions about storage, HDF5 keys, parameter usage, read/write flow, reshaping, file patterns, or data provenance, call io_search.\n"
            "D. If broader background is helpful, call theory_search.\n"
            "E. Then inspect the most relevant source files with repo_read.\n"
            "F. Use repo_search when you need phrase-level confirmation.\n\n"

            "When answering a physical-meaning question, structure the answer using these sections:\n"
            "Code evidence:\n"
            "Project semantic interpretation:\n"
            "General theory background or inference:\n\n"

            "When answering a data-flow or storage question, structure the answer using these sections:\n"
            "Repository I/O evidence:\n"
            "Likely role in the workflow:\n"
            "Uncertainty or follow-up checks:\n\n"

            "Important epistemic rules:\n"
            "- Code evidence has highest priority.\n"
            "- The I/O index summarizes usage patterns but is not a substitute for reading the file.\n"
            "- The semantic map gives project-specific interpretation, but it may contain tentative entries.\n"
            "- Theory glossary gives general background only and must not be presented as proof of repository implementation.\n"
            "- If code evidence is incomplete, say so explicitly.\n"
            "- Do not pretend that a generic DQMC convention is guaranteed to match this repository.\n\n"

            "When asked to create a new script:\n"
            "1. inspect similar existing files first\n"
            "2. use semantic_search if the target quantity has physical meaning implications\n"
            "3. use io_search to infer I/O patterns, HDF5 keys, and parameter usage\n"
            "4. infer repository conventions from source files\n"
            "5. write the script under agent_outputs/\n"
            "6. run check_python\n"
            "7. report saved path and syntax-check result\n\n"

            "Never modify core repository files. Only write under agent_outputs.\n"

            "Termination rules:\n"
            "- Do not call the same search tool repeatedly with near-duplicate queries.\n"
            "- After you have enough evidence from 2-4 relevant files, stop searching and answer.\n"
            "- For physical-meaning questions, do at most:\n"
            "  * 1 repo_index_search\n"
            "  * 1 io_search\n"
            "  * 1 semantic_search\n"
            "  * 1 theory_search\n"
            "  * 2-4 repo_read calls\n"
            "- If uncertainty remains after those steps, answer with explicit uncertainty instead of continuing to search.\n"
            "- Prefer producing a partial but grounded answer over repeated tool use.\n\n"
        ),
        tools=[
            repo_tree,
            repo_read,
            repo_search,
            repo_index_search,
            io_search,
            semantic_search,
            theory_search,
            write_file,
            check_python,
        ],
    )
    return agent