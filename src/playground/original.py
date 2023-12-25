from pathlib import Path
from src.client.agents.http_agent import HTTPAgent
from src.configs import ConfigLoader
from src.typings.config import AssignmentConfig


if __name__ == "__main__":
    conf_folder = Path(__file__).parent.parent.parent / "configs"
    
    task_config = ConfigLoader().load_from(conf_folder / "start_task.yaml")
    assignment_cfg = ConfigLoader().load_from(
        conf_folder / "assignments" / "default.yaml"
    )
    tasks = ConfigLoader().load_from(conf_folder / "tasks" / "task_assembly.yaml")

    agent_name = "gpt-3.5-turbo-0613"
    task_name = "os-std"

    assignment_config = AssignmentConfig.parse_obj(assignment_cfg)
    assignment_config = AssignmentConfig.post_validate(assignment_config)
    agent: HTTPAgent = assignment_config.definition.agent[agent_name].create()