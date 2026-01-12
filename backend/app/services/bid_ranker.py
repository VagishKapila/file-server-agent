def rank_bids(bids):
    """
    bids = list of dicts with:
    landed_unit_price, lead_time_days
    """

    for b in bids:
        b["score"] = (
            (1 / (b["landed_unit_price"] or 1)) * 0.6 +
            (1 / (b.get("lead_time_days", 30))) * 0.4
        )

    return {
        "cheapest": min(bids, key=lambda x: x["landed_unit_price"]),
        "fastest": min(bids, key=lambda x: x.get("lead_time_days", 999)),
        "best_value": max(bids, key=lambda x: x["score"]),
        "all": bids,
    }
