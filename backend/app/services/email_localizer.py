LANGUAGE_INTROS = {
    "es": "Hola, esperamos que estés bien.",
    "pt": "Olá, esperamos que esteja bem.",
    "fr": "Bonjour, nous espérons que vous allez bien.",
    "de": "Hallo, wir hoffen es geht Ihnen gut.",
    "zh": "您好，希望您一切顺利。",
    "en": "Hello, hope you are doing well."
}


def localize_email_intro(country_code: str) -> str:
    return LANGUAGE_INTROS.get(country_code.lower(), LANGUAGE_INTROS["en"])
