import typing as t

import pulumi as p
import requests

from utils.opnsense.base import OpnSenseBaseProvider


def _unbound_override_payload(props: dict[str, t.Any]) -> dict[str, t.Any]:
    return {
        'host': {
            'description': props.get('description', ''),
            'domain': props['domain'],
            'enabled': '1',
            'hostname': props['host'],
            'mx': '',
            'rr': props['record_type'],
            'server': props['ipaddress'],
        },
    }


class HostOverrideProvider(OpnSenseBaseProvider):
    def _reconfigure_unbound(self, client: requests.Session) -> None:
        """
        Reconfigure unbound service.
        """
        response = client.post(self.get_api_path('unbound', 'service', 'reconfigure'), json={})
        response.raise_for_status()
        data = response.json()
        assert data.get('status') == 'ok', 'Failed to reconfigure unbound'

    def create(self, props: dict[str, t.Any]) -> p.dynamic.CreateResult:
        """
        Create new host override.
        """
        client = self.get_client()
        response = client.post(
            self.get_api_path('unbound', 'settings', 'addHostOverride'),
            json=_unbound_override_payload(props),
        )
        response.raise_for_status()
        data = response.json()
        assert data.get('result') == 'saved', 'Failed to create unbound override'
        uuid = data['uuid']

        # Reconfigure unbound to apply the changes
        self._reconfigure_unbound(client)

        return p.dynamic.CreateResult(id_=uuid, outs=props)

    def update(
        self,
        _id: str,
        _olds: dict[str, t.Any],
        _news: dict[str, t.Any],
    ) -> p.dynamic.UpdateResult:
        """
        Update existing host override.
        """
        client = self.get_client()
        response = client.post(
            f'{self.get_api_path("unbound", "settings", "setHostOverride")}/{_id}',
            json=_unbound_override_payload(_news),
        )
        response.raise_for_status()
        data = response.json()
        assert data.get('result') == 'saved', 'Failed to update unbound override'

        # Reconfigure unbound to apply the changes
        self._reconfigure_unbound

        return p.dynamic.UpdateResult(outs=_news)

    def delete(self, _id: str, _props: dict[str, t.Any]) -> None:
        """
        Delete existing host override.
        """
        client = self.get_client()
        response = client.post(
            f'{self.get_api_path("unbound", "settings", "delHostOverride")}/{_id}',
            json={'uuid': _id},
        )
        response.raise_for_status()
        data = response.json()
        assert data.get('result') == 'deleted', 'Failed to delete unbound override'

        # Reconfigure unbound to apply the changes
        self._reconfigure_unbound(client)


class HostOverride(p.dynamic.Resource):
    host: p.Output[str]
    domain: p.Output[str]
    record_type: p.Output[str]
    ipaddress: p.Output[str]
    description: p.Output[str]

    def __init__(
        self,
        name: str,
        host: p.Input[str],
        domain: p.Input[str],
        record_type: p.Input[str],
        ipaddress: p.Input[str],
        description: p.Input[str | None] = None,
        opts: p.ResourceOptions | None = None,
    ):
        super().__init__(
            HostOverrideProvider(),
            name,
            {
                'host': host,
                'domain': domain,
                'record_type': record_type,
                'ipaddress': ipaddress,
                'description': description,
            },
            opts,
        )
