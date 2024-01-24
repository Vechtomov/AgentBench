from src.client.agents.http_agent import HTTPAgent
from src.configs import ConfigLoader
from src.playground.loading import load_configs
from src.playground.prompts import ONE_SHOT
from src.playground.simple_interaction import OSSimpleInteraction
from src.typings.general import InstanceFactory

import time
import logging
from pathlib import Path
from datetime import datetime
import json


date = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")


def configure_logging():
    level = logging.INFO
    logger = logging.getLogger("")
    formatter = logging.Formatter("%(message)s")

    logs_folder = Path(__file__).parent / "logs"
    logs_folder.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(logs_folder / f"os_task-{date}.log")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.setLevel(level)


def main():
    configure_logging()

    base_folder = Path(__file__).parent.parent.parent
    conf_folder = base_folder / "configs"
    data_folder = base_folder / "data" / "os_interaction"
    agents_file = conf_folder / "agents" / "api_agents.yaml"

    agent: HTTPAgent = InstanceFactory.parse_obj(
        ConfigLoader().load_from(agents_file)["gpt-3.5-turbo-0613"]
    ).create()

    config_path = data_folder / "data" / "7" / "simple.json"
    # config_path = data_folder / "data" / "7" / "dev.json"
    script_root_dir = data_folder / "scripts" / "7"
    configs = load_configs(
        config_path=str(config_path), script_root_dir=script_root_dir
    )

    results_folder = Path(__file__).parent / "results"
    results_folder.mkdir(exist_ok=True)
    result_filename = results_folder / f"os_task-{date}.jsonl"
    task = None

    # for cfg in configs[0:1]:
    for cfg in configs:
        try:
            start = time.time()
            task = OSSimpleInteraction(config=cfg, client=agent)
            result = task.run()
            result["history"] = task.history[len(ONE_SHOT) :]
            logging.info(
                "-----FINISH----- %s %s %s",
                result["status"],
                result["result"],
                time.time() - start,
            )
            with open(result_filename, "a") as file:
                json.dump(result, file)
                file.write("\n")
        except KeyboardInterrupt:
            break
        except Exception as ex:
            logging.error("Error", exc_info=ex)
        finally:
            if task is not None:
                task.container.__del__()


if __name__ == "__main__":
    main()
