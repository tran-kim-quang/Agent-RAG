from backend.src.infrastructure.token_stream import ChatTokenStreamPublisher


class FakePipeline:
    def __init__(self) -> None:
        self.commands = []

    def xadd(self, key, fields, **kwargs):
        self.commands.append(("xadd", key, fields, kwargs))
        return self

    def expire(self, key, ttl):
        self.commands.append(("expire", key, ttl))
        return self

    def execute(self):
        self.commands.append(("execute",))


class FakeRedis:
    def __init__(self) -> None:
        self.pipelines = []

    def pipeline(self):
        pipeline = FakePipeline()
        self.pipelines.append(pipeline)
        return pipeline


def test_token_stream_appends_replayable_events_with_ttl() -> None:
    redis = FakeRedis()
    publisher = ChatTokenStreamPublisher(client=redis, ttl_seconds=60)

    publisher.token("run-1", "Xin chao")

    assert redis.pipelines[0].commands == [
        ("xadd", "chat:tokens:run-1", {"type": "token", "content": "Xin chao"}, {"maxlen": 10000, "approximate": True}),
        ("expire", "chat:tokens:run-1", 60),
        ("execute",),
    ]
