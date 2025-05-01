import pulumi as p


def stack_is_prod() -> bool:
    return p.get_stack() == 'prod'
