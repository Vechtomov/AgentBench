import time
from src.client.agent import AgentClient
from src.playground.prompts import SYSTEM_PROMPT, ONE_SHOT
from src.server.tasks.os_interaction.task import Container, JudgeConfig
from src.typings.output import AgentOutput
from src.typings.status import AgentOutputStatus
import re
import itertools
import logging


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


ports = range(2222, 2232)
ports_generator = iter(itertools.cycle(ports))


class OSSimpleInteraction:
    def __init__(self, config: JudgeConfig, client: AgentClient) -> None:
        self.config = config
        self.client = client
        self.history = []
        self.round_limit = 6
        self.port = next(ports_generator)
        self.container = Container("local-os/default", port=self.port)

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

        logging.info("----------DESCRIPTION----------")
        logging.info(self.config.description)
        logging.info("----------HISTORY----------")

        for _ in range(self.round_limit):
            agent_start = time.time()
            try:
                content = self.client.inference(self.history)
                root = AgentOutput(content=content)
            except:
                return {"result": False, "status": "CLIENT_CALL_ERROR"}

            logging.info("---AGENT--- %s", time.time() - agent_start)
            logging.info(root.content)
            logging.info("")
            self.history.append(
                {
                    "role": "agent",
                    "content": root.content,
                }
            )

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
                if len(result) > 1600:
                    result = (
                        result[:1580] + "\n[truncated because the output is too long]"
                    )
                logging.info("---ENV--- %s", time.time() - env_start)
                logging.info(result)
                logging.info("")
                self.history.append(
                    {
                        "role": "user",
                        "content": ("The output of the OS:\n\n" + result)
                        if result
                        else "The output of the OS is empty.",
                    }
                )
        else:
            return {"result": False, "status": "TASK_LIMIT_REACHED"}

        if isinstance(answer, str) and config.match and config.match["strip"]:
            answer = answer.strip()

        jd = False

        last_check = None
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
                    last_check = params
                    jd = False
                    break
                params.append(response.output.decode("utf-8"))
            else:
                jd = True
        else:
            return {"result": False, "status": "UNKNOWN"}

        return {"result": jd, "status": "COMPLETED", "check": last_check}
