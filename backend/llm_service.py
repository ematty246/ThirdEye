from openai import OpenAI

from config import (
    OPENAI_BASE_URL,
    OPENAI_API_KEY,
    LLM_MODEL
)


# =========================================================
# OPENAI-COMPATIBLE CLIENT
# =========================================================

client = OpenAI(
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY
)


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are an AI assistant for a witness-guided forensic
face reconstruction system.

Multiple witnesses may describe the same person.

Your job is to:

1. Combine ALL current witness statements into ONE
   clear natural-language facial reconstruction description.

2. If a previous reconstruction description is provided,
   identify what has changed between the previous and
   current reconstruction.

3. Produce a concise natural-language image-editing
   instruction describing ONLY the visual changes that
   should be made to the previous reconstruction.

IMPORTANT RULES:

- Use only information provided by the witnesses.
- Do not invent facial characteristics.
- Do not assume unspecified characteristics.
- If a witness provides gender, age, hair, eyes, eyebrows,
  nose, mouth, face shape, facial hair, scars, marks,
  or another visible characteristic, preserve that information.
- If a witness corrects an earlier description, use the
  corrected information.
- Preserve all unchanged characteristics.
- The person must remain the same person across
  reconstruction versions.
- Do not use a fixed facial-feature JSON schema.
- Return natural-language descriptions.

For the change instruction:
- Mention ONLY characteristics that changed or were corrected.
- Do not request changes to characteristics that remained unchanged.
- If there is no visual change, say:
  "No visual change."

Return exactly two sections:

CONSOLIDATED DESCRIPTION:
<one natural-language description>

CHANGE INSTRUCTION:
<a concise natural-language instruction for editing the
previous reconstruction, or "No visual change." if this
is the first reconstruction or nothing visually changed>
"""


# =========================================================
# CONSOLIDATE WITNESSES
# =========================================================

def consolidate_witnesses(
    witness_statements,
    previous_description=None
):
    """
    Uses ONE Luna call to produce:

    1. Consolidated reconstruction description
    2. Natural-language change instruction

    No fixed facial-feature JSON schema is used.
    """

    if not witness_statements:
        return {
            "consolidated_description": "",
            "change_instruction": "No visual change."
        }

    # -----------------------------------------------------
    # Format witnesses
    # -----------------------------------------------------

    formatted_witnesses = "\n".join(
        f"Witness {index}: {statement}"
        for index, statement in enumerate(
            witness_statements,
            start=1
        )
    )

    # -----------------------------------------------------
    # Previous reconstruction
    # -----------------------------------------------------

    if previous_description:

        previous_section = f"""
PREVIOUS RECONSTRUCTION:

{previous_description}

Compare the current witness information with this
previous reconstruction.
"""

    else:

        previous_section = """
PREVIOUS RECONSTRUCTION:

None.

This is the first reconstruction.
Therefore the change instruction should be:

No visual change.
"""

    # -----------------------------------------------------
    # User prompt
    # -----------------------------------------------------

    user_prompt = f"""
The following witnesses are describing the same person:

{formatted_witnesses}

{previous_section}

Create the new consolidated reconstruction and determine
what visual characteristics have changed.

Remember:

- The consolidated description must contain all supported
  information from the current witnesses.
- Do not invent details.
- Preserve corrected witness information.
- The change instruction must describe ONLY the changes
  relative to the previous reconstruction.
"""

    # -----------------------------------------------------
    # Luna
    # -----------------------------------------------------

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        temperature=0.2
    )

    content = response.choices[0].message.content.strip()

    # -----------------------------------------------------
    # Parse the two natural-language sections
    # -----------------------------------------------------

    consolidated_description = ""
    change_instruction = "No visual change."

    if "CONSOLIDATED DESCRIPTION:" in content:

        after_description = content.split(
            "CONSOLIDATED DESCRIPTION:",
            1
        )[1]

        if "CHANGE INSTRUCTION:" in after_description:

            description_part, change_part = (
                after_description.split(
                    "CHANGE INSTRUCTION:",
                    1
                )
            )

            consolidated_description = (
                description_part.strip()
            )

            change_instruction = (
                change_part.strip()
            )

        else:

            consolidated_description = (
                after_description.strip()
            )

    else:

        # Fallback if the model does not follow
        # the requested section format.
        consolidated_description = content

    # -----------------------------------------------------
    # Safety fallback
    # -----------------------------------------------------

    if not consolidated_description:

        raise RuntimeError(
            "Luna returned an empty consolidated description."
        )

    if not change_instruction:

        change_instruction = "No visual change."

    return {
        "consolidated_description":
            consolidated_description,

        "change_instruction":
            change_instruction
    }