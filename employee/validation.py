def missing_field(body, field):
    return (
        field not in body
        or body[field] is None
        or (
            isinstance(body[field], str)
            and len(body[field]) == 0
        )
    )


def is_valid_positive_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value > 0
    )