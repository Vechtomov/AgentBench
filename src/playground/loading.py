import json
import os
from typing import List

from src.playground.task_config import TaskConfig


def load_script(script_obj: str | dict, script_root_dir: str):
    if script_obj is None:
        return None

    if type(script_obj) is str:
        return "bash", script_obj

    if "language" not in script_obj:
        language = "bash"
    else:
        language = script_obj["language"]

    if "file" in script_obj:
        with open(
            os.path.join(script_root_dir, script_obj["file"]), encoding="utf-8"
        ) as f:
            return language, f.read()
    elif "code" in script_obj:
        return language, script_obj["code"]
    else:
        raise ValueError("Invalid Script Object")


def load_config_raw(config_path):
    if config_path.endswith(".json"):
        with open(config_path, encoding="utf-8") as f:
            config_raw = json.load(f)
        if isinstance(config_raw, list):
            pass
        elif isinstance(config_raw, dict):
            config_raw = [config_raw]
        else:
            raise ValueError("Invalid Config File")
    elif config_path.endswith(".jsonl"):
        with open(config_path, encoding="utf-8") as f:
            config_raw = [json.loads(line) for line in f.readlines()]
    else:
        raise ValueError("Invalid Config File")

    return config_raw


def parse_config(
    item: dict, script_root_dir: str, default_docker_tag: str
) -> TaskConfig:
    config = TaskConfig()

    config.description = item["description"]

    if "additional_info" in item:
        config.description += item["additional_info"]

    if "explanation" in item:
        config.explanation = item["explanation"]

    if "create" in item:
        config.image = (
            item["create"]["image"]
            if ("image" in item["create"])
            else (default_docker_tag + "/default")
        )
        if "init" in item["create"]:
            if type(item["create"]["init"]) is not list:
                config.init_script = [
                    load_script(item["create"]["init"], script_root_dir)
                ]
            else:
                config.init_script = [
                    load_script(script_obj, script_root_dir)
                    for script_obj in item["create"]["init"]
                ]
        else:
            config.init_script = []
    else:
        config.image = default_docker_tag + "/default"

    evaluation = item["evaluation"]

    if "match" in evaluation:
        if type(evaluation["match"]) is str:
            config.match = {"answer": evaluation["match"], "strip": True}
        else:
            config.match = evaluation["match"]
    elif "check" in evaluation:
        if type(evaluation["check"]) is not list:
            config.check = [load_script(evaluation["check"], script_root_dir)]
        else:
            config.check = [
                load_script(script_obj, script_root_dir)
                for script_obj in evaluation["check"]
            ]
    else:
        raise ValueError("check or match must exist.")

    return config


def load_configs(
    config_path, script_root_dir=".", default_docker_tag="local-os"
) -> List[TaskConfig]:
    config_raw = load_config_raw(config_path)

    return [
        parse_config(item, script_root_dir, default_docker_tag) for item in config_raw
    ]
