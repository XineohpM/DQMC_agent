'''
phoenixm@stanford.edu
Command line interface entry of the DQMC AI agent.
'''

from rich.console import Console
from rich.panel import Panel
from agents.exceptions import MaxTurnsExceeded
from app import agent_config
from app import agent_service

console = Console()

agent = agent_config.build_agent()

def main():
    console.print(Panel.fit(
        "DQMC Repo Agent\n"
        "Recommended tests:\n"
        "  - What is the likely physical meaning of gt0 in this repository?\n"
        "  - Distinguish code evidence and interpretation for jj\n"
        "  - Create a postprocess script for density and double occupancy vs temperature",
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

        result = agent_service.run_once(agent, user_input, max_turns=30)
        if result["ok"]:
            console.print("\n[bold cyan]Agent:[/bold cyan]")
            console.print(result["final_output"])
        else:
            console.print("\n[bold red]Agent error:[/bold red]")
            console.print(result["message"])


if __name__ == "__main__":
    main()