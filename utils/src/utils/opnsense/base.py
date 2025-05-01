import os

import pulumi as p
import requests


class OpnSenseBaseProvider(p.dynamic.ResourceProvider):
    api_key: str
    api_secret: str
    endpoint: str

    def configure(self, req: p.dynamic.ConfigureRequest) -> None:
        self.api_key = os.environ['OPNSENSE_API_KEY']
        self.api_secret = os.environ['OPNSENSE_API_SECRET']
        self.endpoint = os.environ['OPNSENSE_ENDPOINT']
        print(self.api_key, self.api_secret)

    def get_client(self) -> requests.Session:
        client = requests.Session()
        client.auth = (self.api_key, self.api_secret)
        return client

    def get_api_path(self, module: str, controller: str, command: str, *args) -> str:
        return '/'.join([self.endpoint, 'api', module, controller, command, *args])
