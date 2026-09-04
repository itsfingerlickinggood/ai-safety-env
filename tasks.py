from hud import Task, Taskset

# Concrete HUD task row. The environment implementation lives in env.py and is
# joined at runtime by the stable environment name + template id.
_task = Task(
    env="long-horizon-safety-research",
    id="research-sabotage-monitoring",
    args={},
    slug="long-horizon-sabotage-research-001",
    columns={
        "domain": "technical-ai-safety",
        "capability": "forecast-reproduce-critique-extend",
        "difficulty": "long-horizon-pilot",
        "source": "researcharena-grounded-independent-fixtures",
    },
    agent_config={"max_steps": 220, "timeout_seconds": 7200},
)

taskset = Taskset("Long-Horizon AI Safety Research", [_task])
