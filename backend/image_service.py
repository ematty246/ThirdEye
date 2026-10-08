import base64
import io
import requests

from openai import OpenAI
from supabase import create_client

from config import (
    OPENAI_BASE_URL,
    OPENAI_API_KEY,
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================================================
# CLIENTS
# =========================================================

client = OpenAI(
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY
)


supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================================================
# CONFIGURATION
# =========================================================

BUCKET_NAME = "forensic-sketches"

IMAGE_MODEL = "gpt-image-2"


# =========================================================
# COMMON FORENSIC STYLE
# =========================================================

FORENSIC_STYLE = """
Traditional forensic artist pencil sketch.

Style requirements:

- realistic graphite pencil
- black and white
- front-facing head and shoulders
- neutral facial expression
- plain white paper
- realistic facial proportions
- natural pencil shading
- cross-hatching
- professional forensic composite appearance
- no color
- no painting
- no cartoon
- no anime
- no artistic background
- no text
- no watermark
- no police badge
- no extra objects

Do not invent facial characteristics that are not
supported by the witness information.
"""


# =========================================================
# GENERATE INITIAL IMAGE
# =========================================================

def generate_initial_image(
    description: str,
    case_id: str,
    version_number: int
):
    """
    ONLY USED FOR V1.

    Consolidated witness description
        ↓
    New forensic image
        ↓
    Supabase Storage
    """

    # -----------------------------------------------------
    # Safety check
    # -----------------------------------------------------

    if version_number != 1:

        raise RuntimeError(
            "generate_initial_image() can only be used "
            "for reconstruction V1."
        )


    prompt = f"""
Create a realistic forensic facial composite sketch
based STRICTLY on this consolidated witness description:

"{description}"

IMPORTANT:

- Represent only characteristics supported by
  the description.
- Do not invent facial hair.
- Do not invent glasses.
- Do not invent accessories.
- Do not invent scars or marks.
- Do not invent distinctive facial features.
- If something is not specified, keep it neutral.

{FORENSIC_STYLE}
"""


    print()
    print(
        "Generating INITIAL forensic reconstruction..."
    )


    # -----------------------------------------------------
    # Generate image
    # -----------------------------------------------------

    response = client.images.generate(
        model=IMAGE_MODEL,
        prompt=prompt,
        size="1024x1024"
    )


    # -----------------------------------------------------
    # Validate response
    # -----------------------------------------------------

    if not response.data:

        raise RuntimeError(
            "Image generation returned no data."
        )


    image_data = response.data[0].b64_json


    if not image_data:

        raise RuntimeError(
            "Image generation returned no image data."
        )


    image_bytes = base64.b64decode(
        image_data
    )


    if not image_bytes:

        raise RuntimeError(
            "Decoded generated image is empty."
        )


    # -----------------------------------------------------
    # Storage path
    # -----------------------------------------------------

    storage_path = (
        f"{case_id}/"
        f"reconstruction_v{version_number}.png"
    )


    # -----------------------------------------------------
    # Upload
    # -----------------------------------------------------

    supabase.storage \
        .from_(BUCKET_NAME) \
        .upload(
            storage_path,
            image_bytes,
            file_options={
                "content-type": "image/png",
                "upsert": "true"
            }
        )


    # -----------------------------------------------------
    # Public URL
    # -----------------------------------------------------

    image_url = (
        supabase
        .storage
        .from_(BUCKET_NAME)
        .get_public_url(
            storage_path
        )
    )


    print()
    print("Initial image uploaded.")

    print(
        f"Storage path: {storage_path}"
    )

    print(
        f"Image URL: {image_url}"
    )


    return {

        "image_url":
            image_url,

        "storage_path":
            storage_path,

        "generation_id":
            response.data[0].generation_id
    }


# =========================================================
# UPDATE EXISTING RECONSTRUCTION
# =========================================================

def generate_updated_image(
    previous_image_url: str,
    previous_description: str,
    new_description: str,
    change_instruction: str,
    case_id: str,
    version_number: int
):
    """
    V2+ ONLY.

    Previous image
          +
    Updated reconstruction
          +
    Change instruction
          ↓
    Image edit
          ↓
    New version
    """

    # -----------------------------------------------------
    # Safety check
    # -----------------------------------------------------

    if version_number < 2:

        raise RuntimeError(
            "generate_updated_image() can only be used "
            "for reconstruction V2 or later."
        )


    if not previous_image_url:

        raise RuntimeError(
            "Previous image URL is required for "
            "reconstruction V2+."
        )


    # =====================================================
    # EDIT PROMPT
    # =====================================================

    prompt = f"""
Edit the provided forensic facial reconstruction.

PREVIOUS RECONSTRUCTION:

"{previous_description}"


UPDATED RECONSTRUCTION:

"{new_description}"


REQUESTED CHANGE:

"{change_instruction}"


IMPORTANT IDENTITY-PRESERVATION RULES:

The person in the edited image must remain the SAME
person shown in the supplied previous reconstruction.

Preserve every characteristic that has NOT changed.

Only modify characteristics that are explicitly changed
or corrected by the updated witness information.


DO NOT:

- redesign the face
- regenerate a completely different person
- change the identity
- change unchanged facial features
- change face shape unless explicitly requested
- change eyes unless explicitly requested
- change eyebrows unless explicitly requested
- change nose unless explicitly requested
- change mouth unless explicitly requested
- change chin unless explicitly requested
- change hairstyle unless explicitly requested
- add facial hair unless explicitly requested
- add glasses unless explicitly requested
- add accessories unless explicitly requested
- add scars or marks unless explicitly requested
- invent characteristics
- change unrelated facial features


The result must remain visually consistent with the
previous forensic reconstruction.

{FORENSIC_STYLE}
"""


    print()
    print(
        "Updating EXISTING forensic reconstruction..."
    )

    print(
        f"Source image: {previous_image_url}"
    )


    # =====================================================
    # DOWNLOAD PREVIOUS IMAGE
    # =====================================================

    try:

        image_response = requests.get(
            previous_image_url,
            timeout=60
        )

    except requests.RequestException as error:

        raise RuntimeError(
            "Failed to download previous image: "
            f"{str(error)}"
        )


    if image_response.status_code != 200:

        raise RuntimeError(
            "Failed to download previous image. "
            f"HTTP {image_response.status_code}"
        )


    previous_image_bytes = (
        image_response.content
    )


    if not previous_image_bytes:

        raise RuntimeError(
            "Previous image download returned "
            "empty data."
        )


    print(
        f"Downloaded previous image: "
        f"{len(previous_image_bytes)} bytes"
    )


    # =====================================================
    # CREATE FILE-LIKE OBJECT
    # =====================================================

    image_file = io.BytesIO(
        previous_image_bytes
    )

    image_file.name = (
        f"reconstruction_v"
        f"{version_number - 1}.png"
    )


    # =====================================================
    # IMAGE EDIT
    # =====================================================

    print()
    print(
        "Sending previous image to image edit model..."
    )


    try:

        response = client.images.edit(
            model=IMAGE_MODEL,
            image=image_file,
            prompt=prompt,
            size="1024x1024"
        )

    except Exception as error:

        print()
        print(
            "IMAGE EDIT API ERROR:"
        )

        print(
            repr(error)
        )

        raise RuntimeError(
            f"Image edit failed: {str(error)}"
        )


    # =====================================================
    # VALIDATE RESPONSE
    # =====================================================

    if not response.data:

        raise RuntimeError(
            "Image editing returned no data."
        )


    image_data = (
        response.data[0].b64_json
    )


    if not image_data:

        raise RuntimeError(
            "Image editing returned no base64 image."
        )


    # =====================================================
    # DECODE IMAGE
    # =====================================================

    try:

        new_image_bytes = (
            base64.b64decode(
                image_data
            )
        )

    except Exception as error:

        raise RuntimeError(
            "Failed to decode edited image: "
            f"{str(error)}"
        )


    if not new_image_bytes:

        raise RuntimeError(
            "Decoded edited image is empty."
        )


    # =====================================================
    # STORAGE PATH
    # =====================================================

    storage_path = (
        f"{case_id}/"
        f"reconstruction_v{version_number}.png"
    )


    # =====================================================
    # UPLOAD NEW VERSION
    # =====================================================

    try:

        supabase.storage \
            .from_(BUCKET_NAME) \
            .upload(
                storage_path,
                new_image_bytes,
                file_options={
                    "content-type": "image/png",
                    "upsert": "true"
                }
            )

    except Exception as error:

        raise RuntimeError(
            "Failed to upload edited image: "
            f"{str(error)}"
        )


    # =====================================================
    # PUBLIC URL
    # =====================================================

    image_url = (
        supabase
        .storage
        .from_(BUCKET_NAME)
        .get_public_url(
            storage_path
        )
    )


    print()
    print(
        "Updated image uploaded."
    )

    print(
        f"Storage path: {storage_path}"
    )

    print(
        f"Image URL: {image_url}"
    )


    # =====================================================
    # RETURN
    # =====================================================

    return {

        "image_url":
            image_url,

        "storage_path":
            storage_path,

        "generation_id":
            response.data[0].generation_id
    }