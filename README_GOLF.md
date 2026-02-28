# Golf Quantum Analytics Council (GQAC) Integration

This workspace now supports a multi-agent golf analytics system for PGA/Major tournament probability modeling, following the GQAC directive.

## Key Components
- **golf_agents/**: Modular agents for strokes gained, simulation, course, weather, form, and market analysis.
- **.vscode/golf_agents.json**: Agent config and orchestration triggers.
- **system_prompts/golf_council.md**: System prompt for agent collaboration and output protocol.
- **GOLF_IMPLEMENTATION_CHECKLIST.md**: Implementation and validation checklist.
- **scripts/setup_datagolf_api.py**: DataGolf API setup script.
- **scripts/setup_weather_api.py**: Weather API setup script.
- **/data/golf/**: Data storage for SG, course, weather, and tournament info.

## Quick Start
1. Sign up for DataGolf and OpenWeatherMap APIs.
2. Run setup scripts to initialize data.
3. Develop and test agents in `golf_agents/`.
4. Track progress in `GOLF_IMPLEMENTATION_CHECKLIST.md`.

See the GQAC directive for full details and best practices.
