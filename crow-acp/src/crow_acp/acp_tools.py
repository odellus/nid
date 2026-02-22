def tool_match(tool_name: str, terms: tuple[str]) -> bool:
    return any([x in tool_name for x in terms])
