import re


def find_word(text: str):
    # plain word regex (no {/[ structure) outside the flagged shape
    return re.match(r"hello", text)
