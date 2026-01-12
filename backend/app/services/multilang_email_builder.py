LANG_INTRO = {
    "CN": "您好，我们正在为美国的一个项目采购材料。",
    "IT": "Salve, stiamo cercando materiali per un progetto negli Stati Uniti.",
    "BR": "Olá, estamos buscando materiais para um projeto nos EUA.",
    "US": "Hello, we are sourcing materials for a U.S. project."
}

def build_multilang_email(country_code: str, body_en: str):
    intro = LANG_INTRO.get(country_code.upper(), LANG_INTRO["US"])
    return f"""{intro}

{body_en}

Best regards,
Procurement Team
"""
