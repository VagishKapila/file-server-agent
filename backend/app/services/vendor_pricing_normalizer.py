from decimal import Decimal

FX_RATES = {
    "US": Decimal("1.0"),
    "CN": Decimal("0.14"),   # RMB → USD (placeholder, swappable)
    "BR": Decimal("0.20"),   # BRL → USD
}

LANDING_COST = {
    "US": Decimal("1.00"),
    "CN": Decimal("1.18"),   # shipping + duty
    "BR": Decimal("1.15"),
}

def normalize_price(unit_price, country_code):
    fx = FX_RATES.get(country_code, Decimal("1.0"))
    landed = LANDING_COST.get(country_code, Decimal("1.0"))

    usd_price = Decimal(unit_price) * fx
    landed_price = usd_price * landed

    return {
        "fx_rate": fx,
        "landed_unit_price": round(landed_price, 2),
    }
