from __future__ import annotations

import os

import openai
import reflex as rx

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


class ChatappState(rx.State):
    # The current question being asked.
    question: str

    # Keep track of the chat history as a list of (question, answer) tuples.
    chat_history: list[tuple[str, str]]

    def set_question(self, q: str):
        self.question = q

    def set_question1(self, q: str):
        self.question = q

    def set_question2(self, q: str):
        self.question = q

    def set_question3(self, q: str):
        self.question = q

    def answer(self) -> None:
        # Our chatbot is not very smart right now...
        answer = "I don't know!"
        self.chat_history.append((self.question, answer))

    def answer2(self) -> None:
        # Our chatbot is not very smart right now...
        answer = "I don't know!"
        self.chat_history.append((self.question, answer))
        # Clear the question input.
        self.question = ""

    async def answer3(self):
        import asyncio

        # Our chatbot is not very smart right now...
        answer = "I don't know!"
        self.chat_history.append((self.question, ""))

        # Clear the question input.
        self.question = ""
        # Yield here to clear the frontend input before continuing.
        yield

        for i in range(len(answer)):
            await asyncio.sleep(0.1)
            self.chat_history[-1] = (self.chat_history[-1][0], answer[: i + 1])
            yield

    async def answer4(self):
        # Our chatbot has some brains now!
        client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        session = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": self.question}],
            stop=None,
            temperature=0.7,
            stream=True,
        )

        # Add to the answer as the chatbot responds.
        answer = ""
        self.chat_history.append((self.question, answer))

        # Clear the question input.
        self.question = ""
        # Yield here to clear the frontend input before continuing.
        yield

        async for item in session:
            if hasattr(item.choices[0].delta, "content"):
                if item.choices[0].delta.content is None:
                    # presence of 'None' indicates the end of the response
                    break
                answer += item.choices[0].delta.content
                self.chat_history[-1] = (self.chat_history[-1][0], answer)
                yield
