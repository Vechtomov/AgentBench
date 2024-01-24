from typing import List, Tuple


class TaskConfig:
    image: str = None
    init_script: List[Tuple[str, str]] = None
    description: str
    check: list = None
    match: dict = None
    explanation: str = None

    def get_evaluation_type(self):
        if self.check:
            return "check"
        elif self.match:
            return "match"

    def get_evaluation_content(self):
        return self.check or self.match