import json
from src.client.agent import AgentClient
from src.client.agent_test import parse_args
from src.configs import ConfigLoader
from src.typings.general import InstanceFactory
import re
from datetime import datetime

PROMPT = """# PURPOSE
You are a task revisor. You will be given a task description, solution explanation and result evaluation. 
User doesn't see solution explanation and result evaluation, only description.
Your goal is to check that description has all necessary information such as directories, filenames, file extensions and so on to solve the task.

If the description doesn't have some information you have to response with this information after MISSING_INFORMATION tag.
If all the information already exists in the description DO NOT PROVIDE MISSING_INFORMATION tag.
DO NOT INCLUDE the solution into the MISSING_INFORMATION or any hints, how to solve the task. ONLY the actual information such as directories, filenames, file extensions and so on.

# EXAMPLE WITH MISSING INFORMATION IN THE DESCRIPTION
Task Description:
"As a student, you are required to calculate the total size of all files with a specific file extension in a given directory and its subdirectories. You have to use Linux (Ubuntu) operating system commands to achieve this. The file extension and directory path will be given to you as input arguments."

Task Solution Explanation:
"1. First, navigate to the given directory using the 'cd' command.\n2. Then, use the 'find' command to search for all files with the specified file extension.\n3. Use the 'wc' and 'stat' commands to calculate the sizes of the individual files.\n4. Finally, use the 'awk' command to sum up the sizes of all files."

Task Solution Evaluation:
"cd problem_dir\nfind . -type f -iname \"*.txt\" -exec stat -c\"%s\" {} \\; | awk '{total=total+$1} END {print total}'"

Your response:
The task is about calculating the total size of all files with a specific file extension in a given directory and its subdirectories. In description it is said that the file extension and directory path will be given. However, they are not provided. 
From the solution evaluation we can see that the directory should be `problem_dir` and file extension should be `txt`. So the added message to the description should be:
MISSING_INFORMATION:
The directory is 'problem_dir'. The file extension is 'txt'.


# EXAMPLE WITHOUT MISSING INFORMATION
Task Description:
"Design a problem that challenges students to count the number of lines containing the word \"error\" in all files with the extension \".log\" in the current directory (excluding subdirectories). Count only lines where \"error\" appears and is not part of another word. For example, \"errors\" should not be counted. The output should be an integer."

Task Solution Explanation:
"To solve this problem, students need to use various Linux commands to filter and count lines containing the word \"error\" in the specified files. They can use commands like grep, find, wc, and xargs to achieve this.\n\nHint: Students may want to combine the grep and find commands with xargs to filter the appropriate files and lines."

Task Solution Evaluation:
"# The following command can be used to get the standard answer\nfind . -maxdepth 1 -name '*.log' -print0 | xargs -0 grep -iw '\\<error\\>' | wc -l"

Your response:
The task is about counting the number of lines containing the word \"error\" in all files with the extension \".log\" in the current directory. All the information is provided in the task description. So there is nothing to add to the task description.
"""

USER_QUERY = """
Task Description:
"{0}"

Task Solution Explanation:
{1}

Task Solution Evaluation:
{2}
"""


def parse_code_block(input_text: str):
    # Regular expression pattern for finding code blocks
    pattern = r"```(.*?)```"

    # Using re.DOTALL to make '.' match newlines as well
    matches = re.findall(pattern, input_text, re.DOTALL)

    # Return all found code blocks
    return matches


def find_missing_info(input_text: str):
    tag = "MISSING_INFORMATION:"
    index = input_text.rfind(tag)
    if index == -1:
        return None

    return input_text[index + len(tag) :]


date = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

import logging

logging.basicConfig(
    filename=f"fix_tasks-{date}.log", level=logging.INFO, format="%(message)s"
)


def fix_description(
    agent: AgentClient, description: str, explanation: str, evaluation: str
) -> str:
    # Prepare the system prompt
    system_prompt = {"role": "user", "content": PROMPT}
    # Add the problem description to the history
    message = USER_QUERY.format(description, explanation, evaluation)
    logging.info("----------TASK----------")
    logging.info(description)
    history = [{"role": "user", "content": message}]
    # Send the system prompt and problem description to the agent
    agent_response = agent.inference([system_prompt] + history)
    logging.info("")
    logging.info("----------RESPONSE----------")
    logging.info(agent_response)
    logging.info("")
    logging.info("----------------------------")
    logging.info("")
    # Return the agent's response as the fixed description
    return find_missing_info(agent_response)


if __name__ == "__main__":
    args = parse_args()
    loader = ConfigLoader()
    config = loader.load_from(args.config)
    assert args.agent in config, f"Agent {args.agent} not found in {args.config}"
    agent_config = config[args.agent]
    factory = InstanceFactory(**agent_config)
    agent_client: AgentClient = factory.create()

    file_name = "data/os_interaction/data/7/bootstrap.json"
    # Read and parse the bootstrap.json file
    with open(file_name, "r") as file:
        data = json.load(file)

    new_file = []

    for d in data:
        try:
            description = d["description"]
            explanation = d["explanation"]
            evaluation = d["evaluation"]["example"]

            # Send the parsed data to the agent to fix the description
            result = fix_description(agent_client, description, explanation, evaluation)
            if result is not None:
                d["additional_info"] = result

            new_file.append(d)
        except KeyboardInterrupt:
            break
        except Exception as ex:
            print(ex)

    # Save the new file instead of the original
    new_file_name = file_name.replace("bootstrap.json", f"bootstrap_{date}.json")
    with open(new_file_name, "w") as file:
        json.dump(new_file, file)
