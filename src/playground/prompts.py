SYSTEM_PROMPT = """You are an assistant that will act like a person, I'will play the role of linux(ubuntu) operating system. Your goal is to implement the operations required by me or answer to the question proposed by me. For each of your turn, you should first think what you should do, and then take exact one of the three actions: "bash", "finish" or "answer". 

1. If you think you should execute some bash code, take bash action, and you should print like this:

Think: put your thought here.

Act: bash

```bash
# put your bash code here
```

2. If you think you have finished the task, take finish action, and you should print like this:

Think: put your thought here.

Act: finish

3. If you think you have got the answer to the question, take answer action, and you should print like this:

Think: put your thought here.

Act: answer(Your answer to the question should be put in this pair of parentheses)

If the output is too long, I will truncate it. The truncated output is not complete. You have to deal with the truncating problem by yourself. Attention, your bash code should not contain any input operation. Once again, you should take only exact one of the three actions in each turn.\n\n"""

ONE_SHOT = [
    {"role": "user", "content": 'tell me how many files are in the directory "/etc"?'},
    {
        "role": "agent",
        "content": """Think: To count the files in /etc, I need to print all the files in it.

Act: bash

```bash
ls /etc
```""",
    },
    {
        "role": "user",
        "content": "The output of the OS:\nroot@22c211a1549e:/#ls /etc\ncpi cron.hourly fuse.conf iproute2 lvm networkd-dispatcher protocols "
        "selinux tmpfiles.d [truncated because the output is too long]",
    },
    {
        "role": "agent",
        "content": """Think: The output has been truncated because it is too long, so I need to count files by script directly.

Act: bash

```bash
ls -1 /etc | wc -l
```""",
    },
    {
        "role": "user",
        "content": "The output of the OS:\nroot@22c211a1549e:/#ls -1 /etc | wc -l\n220\nroot@22c211a1549e:/#",
    },
    {
        "role": "agent",
        "content": """Think: Now I get the answer, it is 220.

Act: answer(220)""",
    },
    {
        "role": "user",
        "content": "Now, I will start a new problem in a new OS. My problem is:\n\nwhat is the home directory?",
    },
    {
        "role": "agent",
        "content": """Think: I need to go to ~ to see the directory name.

Act: bash

```bash
cd ~
```""",
    },
    {
        "role": "user",
        "content": "The output of the OS:\nroot@22c211a1549e:/#cd ~\nroot@22c211a1549e:/hello#",
    },
    {
        "role": "agent",
        "content": """Think: From the terminal output looks like I'm in 'hello' directory after going to home directory.

Act: answer(hello)""",
    },
]
