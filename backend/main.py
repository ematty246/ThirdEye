from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from database import supabase
from llm_service import consolidate_witnesses
from image_service import (
    generate_initial_image,
    generate_updated_image
)


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="Third Eye API",
    version="1.0.0",
    description="AI-Based Forensic Face Reconstruction System"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# REQUEST MODELS
# =========================================================

class CreateCaseRequest(BaseModel):
    case_name: str


class WitnessRequest(BaseModel):
    statement: str


class UpdateWitnessRequest(BaseModel):
    statement: str


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "message": "Third Eye API is running",
        "version": "1.0.0"
    }


# =========================================================
# CREATE CASE
# =========================================================

@app.post("/cases")
def create_case(request: CreateCaseRequest):

    if not request.case_name.strip():

        raise HTTPException(
            status_code=400,
            detail="Case name cannot be empty"
        )

    try:

        result = (
            supabase
            .table("cases")
            .insert({
                "case_name": request.case_name.strip()
            })
            .execute()
        )

        if not result.data:

            raise HTTPException(
                status_code=500,
                detail="Failed to create case"
            )

        return result.data[0]

    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to create case: {str(error)}"
        )


# =========================================================
# GET ALL CASES
# =========================================================

@app.get("/cases")
def get_cases():

    try:

        response = (
            supabase
            .table("cases")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "cases": response.data or []
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch cases: {str(error)}"
        )


# =========================================================
# ADD WITNESS
# =========================================================

@app.post("/cases/{case_id}/witnesses")
def add_witness(
    case_id: str,
    request: WitnessRequest
):

    if not request.statement.strip():

        raise HTTPException(
            status_code=400,
            detail="Witness statement cannot be empty"
        )

    try:

        # -------------------------------------------------
        # Verify case exists
        # -------------------------------------------------

        case_result = (
            supabase
            .table("cases")
            .select("id")
            .eq("id", case_id)
            .execute()
        )

        if not case_result.data:

            raise HTTPException(
                status_code=404,
                detail="Case not found"
            )

        # -------------------------------------------------
        # Insert witness
        # -------------------------------------------------

        result = (
            supabase
            .table("witnesses")
            .insert({
                "case_id": case_id,
                "statement": request.statement.strip()
            })
            .execute()
        )

        if not result.data:

            raise HTTPException(
                status_code=500,
                detail="Failed to add witness"
            )

        return result.data[0]

    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to add witness: {str(error)}"
        )


# =========================================================
# GET ALL WITNESSES FOR A CASE
# =========================================================

@app.get("/cases/{case_id}/witnesses")
def get_witnesses(case_id: str):

    try:

        # -------------------------------------------------
        # Verify case
        # -------------------------------------------------

        case_result = (
            supabase
            .table("cases")
            .select("id")
            .eq("id", case_id)
            .execute()
        )

        if not case_result.data:

            raise HTTPException(
                status_code=404,
                detail="Case not found"
            )

        # -------------------------------------------------
        # Get witnesses
        # -------------------------------------------------

        result = (
            supabase
            .table("witnesses")
            .select("*")
            .eq("case_id", case_id)
            .order("created_at")
            .execute()
        )

        return {
            "case_id": case_id,
            "witnesses": result.data or []
        }

    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch witnesses: {str(error)}"
        )


# =========================================================
# UPDATE WITNESS
# =========================================================

@app.put("/witnesses/{witness_id}")
def update_witness(
    witness_id: str,
    request: UpdateWitnessRequest
):

    if not request.statement.strip():

        raise HTTPException(
            status_code=400,
            detail="Witness statement cannot be empty"
        )

    try:

        result = (
            supabase
            .table("witnesses")
            .update({
                "statement": request.statement.strip()
            })
            .eq("id", witness_id)
            .execute()
        )

        if not result.data:

            raise HTTPException(
                status_code=404,
                detail="Witness not found"
            )

        return result.data[0]

    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to update witness: {str(error)}"
        )


# =========================================================
# GENERATE RECONSTRUCTION
# =========================================================

@app.post("/cases/{case_id}/reconstruction")
def generate_reconstruction(case_id: str):

    # =====================================================
    # 1. VERIFY CASE
    # =====================================================

    try:

        case_result = (
            supabase
            .table("cases")
            .select("id")
            .eq("id", case_id)
            .execute()
        )

        if not case_result.data:

            raise HTTPException(
                status_code=404,
                detail="Case not found"
            )

    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to verify case: {str(error)}"
        )


    # =====================================================
    # 2. GET ALL CURRENT WITNESSES
    # =====================================================

    try:

        witnesses_result = (
            supabase
            .table("witnesses")
            .select(
                "id, statement, created_at"
            )
            .eq("case_id", case_id)
            .order("created_at")
            .execute()
        )

        witnesses = witnesses_result.data or []

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch witnesses: {str(error)}"
        )


    if not witnesses:

        raise HTTPException(
            status_code=400,
            detail="No witness statements found"
        )


    witness_statements = [
        witness["statement"]
        for witness in witnesses
    ]


    # =====================================================
    # LOGGING
    # =====================================================

    print()
    print("=" * 70)
    print("THIRD EYE - RECONSTRUCTION")
    print("=" * 70)

    print(f"Case ID: {case_id}")
    print(f"Number of witnesses: {len(witness_statements)}")


    # =====================================================
    # 3. GET PREVIOUS RECONSTRUCTION
    # =====================================================

    try:

        previous_result = (
            supabase
            .table("reconstruction_versions")
            .select("*")
            .eq("case_id", case_id)
            .order(
                "version_number",
                desc=True
            )
            .limit(1)
            .execute()
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to fetch previous "
                f"reconstruction: {str(error)}"
            )
        )


    # =====================================================
    # DETERMINE VERSION
    # =====================================================

    if previous_result.data:

        previous_version = previous_result.data[0]

        previous_version_number = int(
            previous_version["version_number"]
        )

        version_number = (
            previous_version_number + 1
        )

        previous_description = (
            previous_version.get(
                "consolidated_description",
                ""
            )
            or ""
        )

        previous_image_url = (
            previous_version.get(
                "image_url"
            )
            or ""
        )

    else:

        previous_version = None

        previous_version_number = 0

        version_number = 1

        previous_description = ""

        previous_image_url = None


    print()
    print(
        f"Previous version: "
        f"{previous_version_number if previous_version else 'None'}"
    )

    print(
        f"New version: V{version_number}"
    )


    # =====================================================
    # 4. ONE LUNA CALL
    # =====================================================

    print()
    print("-" * 70)
    print("STEP 1: GPT-5.6 LUNA")
    print("-" * 70)


    try:

        llm_result = consolidate_witnesses(
            witness_statements=witness_statements,
            previous_description=previous_description
        )

    except Exception as error:

        print()
        print("LLM ERROR:")
        print(repr(error))

        raise HTTPException(
            status_code=500,
            detail=(
                "LLM consolidation failed: "
                f"{str(error)}"
            )
        )


    consolidated = (
        llm_result.get(
            "consolidated_description",
            ""
        )
        or ""
    )


    change_instruction = (
        llm_result.get(
            "change_instruction",
            "No visual change."
        )
        or "No visual change."
    )


    if not consolidated:

        raise HTTPException(
            status_code=500,
            detail="Luna returned an empty reconstruction"
        )


    print()
    print("CONSOLIDATED DESCRIPTION:")
    print(consolidated)

    print()
    print("CHANGE INSTRUCTION:")
    print(change_instruction)


    # =====================================================
    # 5. IMAGE GENERATION / UPDATE
    #
    # EXACT RULE:
    #
    # V1 → INITIAL
    #
    # V2 → EDIT V1
    #
    # V3 → EDIT V2
    #
    # V4 → EDIT V3
    #
    # NEVER generate a new initial image after V1.
    # =====================================================

    print()
    print("-" * 70)
    print("STEP 2: IMAGE GENERATION")
    print("-" * 70)


    try:

        # =================================================
        # V1
        # =================================================

        if version_number == 1:

            print()
            print("MODE: INITIAL IMAGE GENERATION")

            image_result = generate_initial_image(
                description=consolidated,
                case_id=case_id,
                version_number=version_number
            )

            source_image_url = None


        # =================================================
        # V2+
        # =================================================

        else:

            print()
            print("MODE: EXISTING IMAGE UPDATE")


            # -------------------------------------------------
            # Previous image should normally exist
            # -------------------------------------------------

            if not previous_image_url:

                # -------------------------------------------------
                # Recover URL from previous version storage path
                # -------------------------------------------------

                previous_storage_path = (
                    previous_version.get(
                        "storage_path"
                    )
                    if previous_version
                    else None
                )


                if not previous_storage_path:

                    previous_storage_path = (
                        f"{case_id}/"
                        f"reconstruction_v"
                        f"{previous_version_number}.png"
                    )


                previous_image_url = (
                    supabase
                    .storage
                    .from_("forensic-sketches")
                    .get_public_url(
                        previous_storage_path
                    )
                )


                print()
                print(
                    "Previous image URL was missing "
                    "from database."
                )

                print(
                    "Recovered previous image:"
                )

                print(previous_image_url)


            print()
            print(
                f"Previous version: "
                f"V{previous_version_number}"
            )

            print()
            print(
                "Previous image:"
            )

            print(previous_image_url)


            # -------------------------------------------------
            # EDIT PREVIOUS IMAGE
            # -------------------------------------------------

            image_result = generate_updated_image(
                previous_image_url=previous_image_url,
                previous_description=previous_description,
                new_description=consolidated,
                change_instruction=change_instruction,
                case_id=case_id,
                version_number=version_number
            )


            source_image_url = previous_image_url


    except Exception as error:

        print()
        print("=" * 70)
        print("IMAGE GENERATION ERROR")
        print("=" * 70)

        print(repr(error))

        raise HTTPException(
            status_code=500,
            detail=(
                "Image generation/update failed: "
                f"{str(error)}"
            )
        )


    # =====================================================
    # 6. GET GENERATED IMAGE INFORMATION
    # =====================================================

    image_url = image_result.get(
        "image_url"
    )

    storage_path = image_result.get(
        "storage_path"
    )

    generation_id = image_result.get(
        "generation_id"
    )


    if not image_url:

        raise HTTPException(
            status_code=500,
            detail="Image generation returned no image URL"
        )


    print()
    print("IMAGE COMPLETED")

    print()
    print("Storage path:")
    print(storage_path)

    print()
    print("Image URL:")
    print(image_url)


    # =====================================================
    # 7. SAVE RECONSTRUCTION VERSION
    # =====================================================

    print()
    print("-" * 70)
    print("STEP 3: SAVE VERSION")
    print("-" * 70)


    try:

        reconstruction_record = {
            "case_id": case_id,
            "version_number": version_number,
            "consolidated_description": consolidated,
            "image_url": image_url,
            "source_image_url": source_image_url
        }


        # -------------------------------------------------
        # Save storage path and generation ID only if
        # these columns exist in the database.
        #
        # Currently we keep the original schema-safe
        # fields here.
        # -------------------------------------------------

        result = (
            supabase
            .table("reconstruction_versions")
            .insert(
                reconstruction_record
            )
            .execute()
        )


    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to save reconstruction "
                f"version: {str(error)}"
            )
        )


    if not result.data:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to save reconstruction version"
            )
        )


    # =====================================================
    # 8. FINAL RESPONSE
    # =====================================================

    print()
    print("=" * 70)
    print("RECONSTRUCTION COMPLETED")
    print("=" * 70)

    print(
        f"V{version_number} successfully saved."
    )


    return {

        "case_id": case_id,

        "version": version_number,

        "consolidated_description":
            consolidated,

        "change_instruction":
            change_instruction,

        "image_url":
            image_url,

        "source_image_url":
            source_image_url,

        "storage_path":
            storage_path,

        "generation_id":
            generation_id,

        "saved":
            True
    }


# =========================================================
# GET CURRENT RECONSTRUCTION
# =========================================================

@app.get("/cases/{case_id}/reconstruction")
def get_reconstruction(case_id: str):

    try:

        # -------------------------------------------------
        # Verify case
        # -------------------------------------------------

        case_result = (
            supabase
            .table("cases")
            .select("id")
            .eq("id", case_id)
            .execute()
        )

        if not case_result.data:

            raise HTTPException(
                status_code=404,
                detail="Case not found"
            )


        # -------------------------------------------------
        # Get latest reconstruction
        # -------------------------------------------------

        result = (
            supabase
            .table("reconstruction_versions")
            .select("*")
            .eq("case_id", case_id)
            .order(
                "version_number",
                desc=True
            )
            .limit(1)
            .execute()
        )


        if not result.data:

            return {
                "case_id": case_id,
                "reconstruction": None
            }


        return {
            "case_id": case_id,
            "reconstruction": result.data[0]
        }


    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to fetch reconstruction: "
                f"{str(error)}"
            )
        )


# =========================================================
# GET RECONSTRUCTION HISTORY
# =========================================================

@app.get("/cases/{case_id}/reconstruction/history")
def get_reconstruction_history(case_id: str):

    try:

        # -------------------------------------------------
        # Verify case
        # -------------------------------------------------

        case_result = (
            supabase
            .table("cases")
            .select("id")
            .eq("id", case_id)
            .execute()
        )

        if not case_result.data:

            raise HTTPException(
                status_code=404,
                detail="Case not found"
            )


        # -------------------------------------------------
        # Get all versions
        # -------------------------------------------------

        result = (
            supabase
            .table("reconstruction_versions")
            .select("*")
            .eq("case_id", case_id)
            .order("version_number")
            .execute()
        )


        return {
            "case_id": case_id,
            "versions": result.data or []
        }


    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to fetch reconstruction history: "
                f"{str(error)}"
            )
        )