def get_envelope_field(payload: dict, field: str) -> str:
    return str(payload.get(field) or "").strip()
