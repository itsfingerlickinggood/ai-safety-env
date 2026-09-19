from hud import Task


task = Task(
    env="ai-safety-monitoring-regression",
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
