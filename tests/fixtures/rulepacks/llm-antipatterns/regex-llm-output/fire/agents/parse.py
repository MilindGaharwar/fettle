import re


def parse_llm_reply(reply: str):
    return re.search(r"\{.*\}", reply)
