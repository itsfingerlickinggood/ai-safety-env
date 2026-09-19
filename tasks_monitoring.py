from hud import Task, Taskset


taskset = Taskset(
    "AI Safety Monitoring Regression",
    [
        Task(
            env="ai-safety-monitoring-regression",
            id="research-sabotage-monitoring",
            args={},
            slug="long-horizon-sabotage-research-001",
            columns={
                "domain": "technical-ai-safety",
                "capability": "forecast-reproduce-critique-extend",
                "difficulty": "long-horizon-regression",
                "source": "researcharena-grounded-independent-fixtures",
                "claim_boundary": "synthetic-monitoring-regression",
            },
            agent_config={"max_steps": 220, "timeout_seconds": 7200},
        )
    ],
)
