from hud import Task, Taskset


taskset = Taskset(
    "AI Safety Paper Reproduction - Core v1",
    [
        Task(
            env="optstop-core-reproduction-v1",
            id="optstop-core-reproduction-v1",
            args={},
            slug="optstop-core-reproduction-v1-001",
            columns={
                "domain": "technical-ai-safety",
                "capability": "forecast-reproduce-critique",
                "difficulty": "long-horizon-paper-reproduction",
                "source": "Pilditch-2026-optstop-independent-current-model-study",
                "claim_boundary": "bounded-independent-core-reproduction",
            },
            agent_config={"max_steps": 120, "timeout_seconds": 7200},
        )
    ],
)
