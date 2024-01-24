import time
from src.client.agent import AgentClient
from src.playground.prompts import SYSTEM_PROMPT, ONE_SHOT
from src.playground.task_config import TaskConfig
from src.server.tasks.os_interaction.task import Container
from src.typings.output import AgentOutput
from src.typings.status import AgentOutputStatus
import re
import itertools
import logging
from enum import Enum, auto


class TaskStatus(Enum):
    UNKNOWN = auto()
    COMPLETED = auto()
    ANSWER = auto()
    CLIENT_CALL_ERROR = auto()
    AGENT_VALIDATION_FAILED = auto()
    AGENT_INVALID_ACTION = auto()
    TASK_LIMIT_REACHED = auto()
    NUMBER_OF_ACTIONS_FAILED = auto()


class Stages(Enum):
    FIRST_ATTEMPT = auto()
    SECOND_ATTEMPT = auto()
    HINT = auto()
    SOLUTION = auto()


def extract_action(raw: str):
    think_pattern = r"Think:\s*(.+)"
    act_pattern = r"Act:\s*(.+)"

    think = re.findall(think_pattern, raw)
    actions = re.findall(act_pattern, raw)

    if len(actions) != 1:
        return None

    ret = {"thought": "\n".join(think), "action": None, "content": None}

    action = actions[0]

    if action.lower().startswith("bash"):
        ret["action"] = "bash"
    elif action.lower().startswith("finish"):
        ret["action"] = "commit"
    elif action.lower().startswith("answer"):
        content = action[6:].strip()
        left_par_pos = content.find("(")
        right_par_pos = content.rfind(")")
        content = content[left_par_pos + 1 : right_par_pos]
        ret["action"] = "commit"
        ret["content"] = content

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
    def __init__(self, config: TaskConfig, client: AgentClient) -> None:
        self.config = config
        self.client = client
        self.history = []
        self.round_limit = 6
        self.port = next(ports_generator)
        self.container = Container("local-os/default", port=self.port)

    def run(self):
        self._init_scripts()

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

        result = False
        check_details = None

        stages = [Stages.FIRST_ATTEMPT, Stages.SECOND_ATTEMPT, Stages.HINT]
        num_attempts = len(stages) - 1

        for i, s in enumerate(stages):
            status, info = self._round()
            if status == TaskStatus.ANSWER:
                result, check_details = self._evaluate(answer=info)
                if result or i == num_attempts:
                    break

                next_stage = stages[i + 1]
                if next_stage == Stages.SECOND_ATTEMPT:
                    self.history.append(
                        {
                            "role": "user",
                            "content": "This is the wrong answer, I give you another attempt. Try to think carefully and check your answer.",
                        }
                    )
                elif next_stage == Stages.HINT:
                    if self.config.explanation is not None:
                        self.history.append(
                            {
                                "role": "user",
                                "content": "This is the wrong answer, I give you a hint. You should follow these steps: "
                                + self.config.explanation,
                            }
                        )
                    else:
                        break

            else:
                if i == num_attempts:
                    return {
                        "result": False,
                        "status": TaskStatus.TASK_LIMIT_REACHED.name,
                    }

                if status == TaskStatus.AGENT_INVALID_ACTION:
                    self.history.append(
                        {
                            "role": "user",
                            "content": f"Error: Looks like you provided invalid action name: {info}",
                        }
                    )
                elif status == TaskStatus.AGENT_VALIDATION_FAILED:
                    self.history.append(
                        {
                            "role": "user",
                            "content": "Error: Looks like you didn't provide a valid action",
                        }
                    )
                elif status == TaskStatus.TASK_LIMIT_REACHED:
                    self.history.append(
                        {
                            "role": "user",
                            "content": "Warning: Looks like you have almost reached the limit of attempts. Maybe you trying the same thing? Try to change your strategy.",
                        }
                    )
                elif status == TaskStatus.NUMBER_OF_ACTIONS_FAILED:
                    self.history.append(
                        {
                            "role": "user",
                            "content": "Error: You should provide only one action at a conversation round.",
                        }
                    )

        return {
            "result": result,
            "status": TaskStatus.COMPLETED.name,
            "check": check_details,
        }

    def _init_scripts(self):
        if self.config.init_script:
            for script in self.config.init_script:
                self.container.execute_independent(script)

    def _round(self):
        for _ in range(self.round_limit):
            agent_start = time.time()
            try:
                content = self.client.inference(self.history)
                root = AgentOutput(content=content)
            except:
                return TaskStatus.CLIENT_CALL_ERROR, None

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
            if root is None:
                return TaskStatus.NUMBER_OF_ACTIONS_FAILED, None
            if "action" not in root or root["action"] is None:
                return TaskStatus.AGENT_VALIDATION_FAILED, None
            if root["action"] not in ["bash", "commit"]:
                return TaskStatus.AGENT_INVALID_ACTION, root["action"]

            action = root["action"]
            content = root["content"]
            if action == "commit":
                return TaskStatus.ANSWER, content
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

        return TaskStatus.TASK_LIMIT_REACHED, None

    def _evaluate(self, answer):
        config = self.config

        if isinstance(answer, str) and config.match and config.match["strip"]:
            answer = answer.strip()

        details = None

        if config.match:
            if "answer" in config.match:
                return answer == config.match["answer"], [
                    answer,
                    config.match["answer"],
                ]
            elif "regex" in config.match:
                return re.search(config.match["regex"], answer) is not None, [
                    answer,
                    config.match["regex"],
                ]
        elif config.check:
            params = [str(answer)] if answer is not None else []
            for script in config.check:
                response = self.container.execute_independent(script, *params)
                if response.exit_code != 0:
                    details = list(map(lambda x: x.strip(), params))
                    return False, details
                params.append(response.output.decode("utf-8"))
            else:
                return True, details
        else:
            return False, "Config error"
