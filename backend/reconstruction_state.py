from datetime import datetime


def create_new_case():
    """
    Creates a new reconstruction case.
    """

    return {
        "witnesses": [],
        "current_reconstruction": "",
        "reconstruction_history": []
    }


def add_witness(case, statement):
    """
    Adds a new witness statement to the case.
    """

    witness = {
        "id": len(case["witnesses"]) + 1,
        "statement": statement,
        "created_at": datetime.now().isoformat()
    }

    case["witnesses"].append(witness)

    return case


def update_witness(case, witness_id, new_statement):
    """
    Updates an existing witness statement.
    """

    for witness in case["witnesses"]:

        if witness["id"] == witness_id:

            witness["statement"] = new_statement
            witness["updated_at"] = datetime.now().isoformat()

            break

    return case


def get_witness_statements(case):
    """
    Returns all current witness statements.
    """

    return [
        witness["statement"]
        for witness in case["witnesses"]
    ]


def save_reconstruction(case, reconstruction):
    """
    Saves the new consolidated reconstruction and
    preserves the previous reconstruction in history.
    """

    if case["current_reconstruction"]:

        previous_version = {
            "version": len(case["reconstruction_history"]) + 1,
            "description": case["current_reconstruction"],
            "created_at": datetime.now().isoformat()
        }

        case["reconstruction_history"].append(previous_version)

    case["current_reconstruction"] = reconstruction

    return case