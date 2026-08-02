import re


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Za-z0-9-]+"
    r"(?:\.[A-Za-z0-9-]+)*"
    r"\.[A-Za-z]{2,}$"
)


def is_valid_email(email):
    if not isinstance(email, str):
        return False

    return EMAIL_PATTERN.fullmatch(email) is not None