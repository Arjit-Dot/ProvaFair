"""Use cases: turn winner indices into meaningful labels."""
USE_CASES = {
    "ipo": {"label": "IPO allotment", "noun": "applicant", "default_pool": 500, "default_winners": 5},
    "lottery": {"label": "Lottery", "noun": "ticket", "default_pool": 1000, "default_winners": 4},
    "validator": {"label": "Blockchain validator selection", "noun": "validator", "default_pool": 128, "default_winners": 7},
}


def label(use_case: str, idx: int) -> str:
    if use_case == "ipo":
        return f"APP-{idx + 1:05d} (PAN ***{(idx * 7919) % 9000 + 1000}K)"
    if use_case == "validator":
        return f"validator-0x{(idx * 2654435761) % 0xFFFFFF:06x}"
    return f"Ticket #{idx + 1:06d}"


def labels(use_case: str, indices):
    return [label(use_case, i) for i in indices]
