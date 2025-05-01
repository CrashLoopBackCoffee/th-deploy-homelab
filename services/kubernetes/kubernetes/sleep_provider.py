import time

import pulumi as p


class SleepProvider(p.dynamic.ResourceProvider):
    def create(self, props):
        time.sleep(props['time'])
        return p.dynamic.CreateResult(id_='dummy', outs=props)


class SleepResource(p.dynamic.Resource):
    """
    Fake resource which takes some time to create.
    """

    def __init__(self, name, time, opts=None):
        super().__init__(SleepProvider(), name, {'time': time}, opts)
