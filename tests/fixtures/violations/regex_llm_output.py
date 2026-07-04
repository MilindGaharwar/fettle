import re
response_text = "Some LLM output with [data] in {brackets}"
match = re.search(r'\[([^\]]+)\]', response_text)
