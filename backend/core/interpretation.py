def build_basic_summary(result: dict) -> str:
    band = result.get("risk_band", "unknown")
    flags = result.get("flags", [])

    parts = [f"Risk band: {band}."]
    if flags:
        parts.append("Flags: " + ", ".join(flags))
    return " ".join(parts)
