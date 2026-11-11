"""QA stub (db_upgrade cluster): fake OpenAI-compatible streaming client, opt-in via AI_PROVIDER=qa_stub.

The sandbox cannot reach any LLM provider; this returns canned tokens shaped like
openai's ChatCompletionChunk (`item.choices[0].delta.content`), ending with a None delta.
"""

import time
from types import SimpleNamespace

TOKENS = ["**Stubbed** ", "answer ", "to: ", "{prompt}", " — ", "token-", "stream ", "done."]


def _chunk(text):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])


class _Completions:
    def create(self, model, messages, **kwargs):
        prompt = messages[-1]["content"]

        def gen():
            for t in TOKENS:
                time.sleep(0.05)
                yield _chunk(t.format(prompt=prompt))
            yield _chunk(None)

        return gen()


class FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_Completions())
