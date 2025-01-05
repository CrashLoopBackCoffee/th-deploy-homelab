import functools
import typing as t
import urllib.parse

import pulumi as p
import pulumi_onepassword as onepassword


@functools.cache
def _get_provider() -> onepassword.Provider:
    return onepassword.Provider('1password')


class OnePasswordItem(t.NamedTuple):
    """
    Represents a 1Password item reference. Uses named tuple to be hashable.
    """

    vault: str
    item: str
    field: str


def _parse_op_ref(secret_ref: str):
    """Parses a 1Password secret reference

    E.g. op://Pulumi/Test Login New/password becomed
    vault: Pulumi
    item: Test Login New
    field: password
    """
    parts = urllib.parse.urlparse(secret_ref)
    vault = parts.netloc
    item, field = parts.path.lstrip('/').split('/', 1)
    return OnePasswordItem(vault, item, field)


@functools.cache
def _fetch_item(item_ref: OnePasswordItem):
    provider = _get_provider()
    return onepassword.get_item_output(
        vault=item_ref.vault,
        title=item_ref.item,
        opts=p.InvokeOptions(provider=provider),
    )


def resolve_secret_ref(secret_ref: str) -> p.Output[str]:
    item_ref = _parse_op_ref(secret_ref)
    item = _fetch_item(item_ref)
    return p.Output.secret(getattr(item, item_ref.field))
