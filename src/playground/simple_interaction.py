import json
import time
from src.client.agent import AgentClient
from src.playground.prompts import SYSTEM_PROMPT, ONE_SHOT
from src.server.tasks.os_interaction.task import Container, JudgeConfig
from src.typings.output import AgentOutput
from src.typings.status import AgentOutputStatus
import re
import random

def extract_action(raw: str):
    think_pattern = r"Think:\s*(.+)"
    act_pattern = r"Act:\s*(.+)"

    think = re.findall(think_pattern, raw)
    act = re.findall(act_pattern, raw)

    ret = {"thought": "\n".join(think), "action": None, "content": None}

    # reversly iterate over the action list
    for action in act[::-1]:
        if action.lower().startswith("bash"):
            ret["action"] = "bash"
            break
        if action.lower().startswith("finish"):
            ret["action"] = "commit"
            break
        if action.lower().startswith("answer"):
            content = action[6:].strip()
            left_par_pos = content.find("(")
            right_par_pos = content.rfind(")")
            if left_par_pos == -1 or right_par_pos == -1:
                continue
            content = content[left_par_pos + 1 : right_par_pos]
            ret["action"] = "commit"
            ret["content"] = content
            break

    if ret["action"] == "bash":
        # extract from ```bash to ```
        content_pattern = r"```bash\n(.*?)\n```"
        content = re.findall(content_pattern, raw, re.DOTALL)
        content = "\n\n".join(content)
        ret["content"] = content

    return ret


class OSSimpleInteraction:
    
    def __init__(self, config: JudgeConfig, client: AgentClient) -> None:
        self.config = config
        self.client = client
        self.history = []
        self.round_limit = 6
        # port = random.randint(2222, 2232)
        port = 2222
        self.container = Container("local-os/default", port=port)

    def run(self):
        config = self.config
        if self.config.init_script:
            for script in self.config.init_script:
                self.container.execute_independent(script)

        if self.config.start:
            self.container.execute(self.config.start[1])

        initial_message = (
            SYSTEM_PROMPT + "Now, my problem is:\n\n" + ONE_SHOT[0]["content"]
        )
        self.history.append({"role": "user", "content": initial_message})

        for item in ONE_SHOT[1:]:
            self.history.append(item)

        self.history.append(
            {
                "role": "user",
                "content": "Now, I will start a new problem in a new OS. My problem is:\n\n"
                + self.config.description,
            }
        )

        print("----------DESCRIPTION----------")
        print(self.config.description)
        print("----------HISTORY----------")

        for _ in range(self.round_limit):
            agent_start = time.time()
            content = self.client.inference(self.history)
            root = AgentOutput(content=content)
            if root.status == AgentOutputStatus.AGENT_CONTEXT_LIMIT:
                return {"result": False, "status": "AGENT_CONTEXT_LIMIT"}
            if root.status != AgentOutputStatus.NORMAL:
                return {"result": False, "status": "UNKNOWN"}
            print("---AGENT---", time.time() - agent_start)
            print(root.content)
            print()
            root = extract_action(root.content)
            if "action" not in root:
                return {"result": False, "status": "AGENT_VALIDATION_FAILED"}
            if root["action"] not in ["bash", "commit"]:
                return {"result": False, "status": "AGENT_INVALID_ACTION"}

            action = root["action"]
            content = root["content"]
            if action == "commit":
                answer = content
                break
            elif action == "bash":
                env_start = time.time()
                result = self.container.execute(content)
                result = result.output
                if len(result) > 800:
                    result = (
                        result[:780] + "\n[truncated because the output is too long]"
                    )
                print("---ENV---", time.time() - env_start)
                print(result)
                print()
                self.history.append(
                    {
                        "role": "user",
                        "content": ("The output of the OS:\n\n" + result)
                        if result
                        else "The output of the OS is empty.",
                    }
                )
        else:
            return (
                {
                    "result": False,
                    "status": "TASK_LIMIT_REACHED",
                },
            )

        if isinstance(answer, str) and config.match and config.match["strip"]:
            answer = answer.strip()

        jd = False

        if config.match:
            if "answer" in config.match:
                jd = answer == config.match["answer"]
            elif "regex" in config.match:
                jd = re.search(config.match["regex"], answer) is not None
        elif config.check:
            params = [str(answer)]
            for script in config.check:
                if script is None:
                    script = config.example_script
                response = self.container.execute_independent(script, *params)
                if response.exit_code != 0:
                    jd = False
                    break
                params.append(response.output.decode("utf-8"))
            else:
                jd = True
        else:
            return {"result": False, "reason": "UNKNOWN"}

        return {
            "result": jd,
            "status": "COMPLETED",
        }
