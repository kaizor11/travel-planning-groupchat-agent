import json


def _build_json_prompt(
    user_text: str,
    schema: dict,
    prompt_rules: tuple[str, ...],
    current_date: str,
    user_timezone: str,
    task_description: str,
) -> str:
    schema_text = json.dumps(schema, ensure_ascii=False, indent=2)
    rules_text = "\n".join(
        f"{index}. {rule}" for index, rule in enumerate(prompt_rules, start=1)
    )

    return (
        "You are a travel search assistant.\n"
        f"Today's date is {current_date}.\n"
        f"The user's timezone is {user_timezone}.\n\n"
        f"{task_description}\n"
        "Return JSON only.\n"
        "Do not return markdown.\n"
        "Do not return explanations.\n"
        "All fields must strictly follow the schema below.\n\n"
        "Schema:\n"
        f"{schema_text}\n\n"
        "Rules:\n"
        f"{rules_text}\n\n"
        "User input:\n"
        f"{user_text}"
    )


def build_intent_detection_prompt(
    user_text: str,
    schema: dict,
    prompt_rules: tuple[str, ...],
    current_date: str,
    user_timezone: str,
) -> str:
    return _build_json_prompt(
        user_text=user_text,
        schema=schema,
        prompt_rules=prompt_rules,
        current_date=current_date,
        user_timezone=user_timezone,
        task_description=(
            "Classify the user's travel request intent as structured JSON and "
            "set the intent field to the best matching supported value."
        ),
    )


def build_extraction_prompt(
    user_text: str,
    schema: dict,
    prompt_rules: tuple[str, ...],
    current_date: str,
    user_timezone: str,
) -> str:
    return _build_json_prompt(
        user_text=user_text,
        schema=schema,
        prompt_rules=prompt_rules,
        current_date=current_date,
        user_timezone=user_timezone,
        task_description="Convert the user's request into structured JSON for the selected travel schema.",
    )
