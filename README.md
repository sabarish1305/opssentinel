# OpsSentinel

OpsSentinel is an evidence-first incident response agent built on TrueForge.

Its goal is to investigate service incidents, gather evidence through tools, run diagnostics safely, and require explicit human approval before taking irreversible recovery actions such as a rollback.

## Project status

Early hackathon development.

Current foundation includes:

- Python project structure
- Isolated virtual environment
- Pytest test configuration
- Initial package and test setup

## Planned workflow

Incident detected  
→ Observe system state  
→ Gather deployment and service evidence  
→ Diagnose the likely root cause  
→ Run diagnostics in a sandbox  
→ Prepare a recovery action  
→ Request human approval  
→ Execute the approved action  
→ Verify service recovery

## Safety model

OpsSentinel uses progressive action levels:

- **Observe** — read system information
- **Diagnose** — analyze evidence and run safe diagnostics
- **Prepare** — formulate a proposed recovery action
- **Act** — perform a state-changing action only after human approval

## Tech stack

- TrueForge
- Python
- Model Context Protocol (MCP)
- Docker
- GitHub
- Qodo
- Pytest

## Development

This project is being built during the Agent Harness Hackathon.

AI coding assistance is used during development and will be disclosed in the final submission. All code is reviewed, tested, and understood by the participant before being submitted.

## Local development

Create and activate a Python 3.12 virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate