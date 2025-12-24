def build_call_summary(
    company: str,
    trade: str,
    open_to_bid: bool,
    wants_job_walk: bool,
    bid_days: int | None,
    availability: list[str]
) -> str:
    lines = []

    lines.append(f"Spoke with {company} ({trade}).")

    if open_to_bid:
        lines.append("They are open to bidding.")
        if bid_days:
            lines.append(f"Estimated bid turnaround is about {bid_days} days.")
    else:
        lines.append("They are not interested in bidding at this time.")

    if wants_job_walk:
        if availability:
            lines.append(
                "They are open to a job walk. Availability: "
                + ", ".join(availability)
            )
        else:
            lines.append("They are open to a job walk and will follow up on availability.")
    else:
        lines.append("They do not feel a job walk is necessary.")

    return " ".join(lines)
