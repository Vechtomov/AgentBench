import time
from src.client.agents.http_agent import HTTPAgent
from src.configs import ConfigLoader
from src.playground.loading import load_configs
from src.playground.simple_interaction import OSSimpleInteraction
from pathlib import Path

from src.typings.general import InstanceFactory

def main():
    base_folder = Path(__file__).parent.parent.parent
    conf_folder = base_folder / "configs"
    data_folder = base_folder / "data" / "os_interaction"
    agent_file = conf_folder / "agents" / "openai-chat.yaml"

    agent: HTTPAgent = InstanceFactory.parse_obj(ConfigLoader().load_from(agent_file)).create()
    
    config_path = data_folder / "data" / "7" / "small.json"
    script_root_dir = data_folder / "scripts" / "7"
    configs = load_configs(config_path=str(config_path), script_root_dir=script_root_dir)
    
    for cfg in configs:
        try:
            start = time.time()
            task = OSSimpleInteraction(config=cfg, client=agent)
            task.run()
            print("-----FINISH-----", time.time() - start)
        finally:
            try:
                task.container.__del__()
                time.sleep(1)
            except:
                pass

if __name__ == "__main__":
    main()