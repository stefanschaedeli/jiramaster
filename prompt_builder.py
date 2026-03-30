from config import load_prompt_template

MEETING_NOTES_PLACEHOLDER = "{{MEETING_NOTES}}"
TUNING_PLACEHOLDER = "{{TUNING_INSTRUCTIONS}}"

SAMPLE_INSTRUCTION = (
    "(No meeting notes provided — generate a realistic sample output "
    "with 2–3 Epics and their Stories.)"
)

AGGRESSIVENESS_MAP = {
    1: "Extract ONLY explicit decisions, commitments, and major deliverables. Ignore minor tasks, discussion points, and vague mentions.",
    2: "Extract significant actions and deliverables. Include clear next steps but skip minor discussion items.",
    3: "Extract ALL action items, tasks, and activities mentioned, even brief or tentative ones.",
}

DETAIL_LEVEL_MAP = {
    "Brief": "For each Story, provide only: title and a one-sentence description. Leave all other fields empty.",
    "Standard": "For each Story, provide all fields: title, description, acceptance_criteria, due_date, priority, assignee, comment.",
    "Detailed": "For each Story, provide all fields with thorough descriptions. Write acceptance criteria as a numbered checklist. Include specific examples where relevant.",
}

SUBTASKS_FORMAT = """\
      subtasks:
        - "Sub-task title 1"
        - "Sub-task title 2" """


def build_tuning_instructions(tuning: dict) -> str:
    aggressiveness = int(tuning.get("aggressiveness", 2))
    stories_min = int(tuning.get("stories_min", 2))
    stories_max = int(tuning.get("stories_max", 6))
    detail_level = tuning.get("detail_level", "Standard")
    include_subtasks = tuning.get("include_subtasks", False)

    lines = [
        "RULES:",
        f"- {AGGRESSIVENESS_MAP.get(aggressiveness, AGGRESSIVENESS_MAP[2])}",
        f"- Each Epic must have between {stories_min} and {stories_max} Stories.",
        f"- {DETAIL_LEVEL_MAP.get(detail_level, DETAIL_LEVEL_MAP['Standard'])}",
        "- Output ONLY valid YAML — no markdown fences, no explanations, no extra text.",
        "- Use ISO 8601 format for dates (YYYY-MM-DD) or leave empty string if unknown.",
        "- Priority must be one of: Low, Medium, High, Critical.",
        "- Assignee is a free-text name (leave empty if unknown).",
        "- acceptance_criteria is REQUIRED for every Epic and every Story. Write it as 1–5 concrete, testable statements (e.g. Given/When/Then or a numbered checklist). Never leave it as '...' or empty.",
    ]

    if include_subtasks:
        lines.append('- Each Story must also have a \'subtasks\' list with 2-4 brief sub-task titles.')

    return "\n".join(lines)


def build_prompt(meeting_notes: str, tuning: dict = None) -> str:
    if tuning is None:
        tuning = {}

    template = load_prompt_template()
    tuning_block = build_tuning_instructions(tuning)

    if TUNING_PLACEHOLDER in template:
        template = template.replace(TUNING_PLACEHOLDER, tuning_block)
    else:
        # Legacy template without tuning placeholder — prepend tuning block
        template = tuning_block + "\n\n" + template

    notes_content = meeting_notes.strip() if meeting_notes else ""
    if not notes_content:
        notes_content = SAMPLE_INSTRUCTION

    if MEETING_NOTES_PLACEHOLDER in template:
        return template.replace(MEETING_NOTES_PLACEHOLDER, notes_content)
    return template + "\n\n" + notes_content
