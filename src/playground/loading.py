
import json
import os
from typing import List

from src.server.tasks.os_interaction.task import JudgeConfig

def load_configs(config_path, script_root_dir=".", default_docker_tag = "local-os") -> List[JudgeConfig]:
    def load_script(script_obj):
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

    # 1. handle input file:
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

    # 2. handle configs
    configs: list[JudgeConfig] = []
    for item in config_raw:
        config = JudgeConfig()
        config.description = item["description"]
        if "additional_info" in item:
            config.description += item["additional_info"]
        if "create" in item:
            config.image = (
                item["create"]["image"]
                if ("image" in item["create"])
                else (default_docker_tag + "/default")
            )
            if "init" in item["create"]:
                if type(item["create"]["init"]) is not list:
                    config.init_script = [load_script(item["create"]["init"])]
                else:
                    config.init_script = [
                        load_script(script_obj)
                        for script_obj in item["create"]["init"]
                    ]
            else:
                config.init_script = []
        else:
            config.image = default_docker_tag + "/default"
        if "start" in item:
            config.start = load_script(item["start"])
        evaluation = item["evaluation"]
        if "match" in evaluation:
            if type(evaluation["match"]) is str:
                config.match = {"answer": evaluation["match"], "strip": True}
            else:
                config.match = evaluation["match"]
        elif "check" in evaluation:
            if type(evaluation["check"]) is not list:
                config.check = [load_script(evaluation["check"])]
            else:
                config.check = [
                    load_script(script_obj) for script_obj in evaluation["check"]
                ]
        else:
            raise ValueError("check or match must exist.")
        if "check" in evaluation and "example" in evaluation:
            config.example_script = load_script(evaluation["example"])
        configs.append(config)
    return configs