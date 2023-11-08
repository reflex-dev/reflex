import asyncio

import reflex as rx

from ..state import State

# openai.api_key = os.environ["OPENAI_API_KEY"]
# openai.api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")


class QA(rx.Base):
    """A question and answer pair."""

    question: str
    answer: str


DEFAULT_CHATS = {
    "Intros": [],
}


class State(State):
    """The app state."""

    # A dict from the chat name to the list of questions and answers.
    chats: dict[str, list[QA]] = DEFAULT_CHATS

    # The current chat name.
    current_chat = "Intros"

    # The current question.
    question: str

    # Whether we are processing the question.
    processing: bool = False

    # The name of the new chat.
    new_chat_name: str = ""

    # Whether the drawer is open.
    drawer_open: bool = False

    # Whether the modal is open.
    modal_open: bool = False

    def create_chat(self):
        """Create a new chat."""
        # Add the new chat to the list of chats.
        self.current_chat = self.new_chat_name
        self.chats[self.new_chat_name] = []

        # Toggle the modal.
        self.modal_open = False

    def toggle_modal(self):
        """Toggle the new chat modal."""
        self.modal_open = not self.modal_open

    def toggle_drawer(self):
        """Toggle the drawer."""
        self.drawer_open = not self.drawer_open

    def delete_chat(self):
        """Delete the current chat."""
        del self.chats[self.current_chat]
        if len(self.chats) == 0:
            self.chats = DEFAULT_CHATS
        self.current_chat = list(self.chats.keys())[0]
        self.toggle_drawer()

    def set_chat(self, chat_name: str):
        """Set the name of the current chat.

        Args:
            chat_name: The name of the chat.
        """
        self.current_chat = chat_name
        self.toggle_drawer()

    @rx.var
    def chat_titles(self) -> list[str]:
        """Get the list of chat titles.

        Returns:
            The list of chat names.
        """
        return list(self.chats.keys())

    async def process_question(self, form_data: dict[str, str]):
        """Get the response from the API.

        Args:
            form_data: A dict with the current question.

        Yields:
            The current question and the response.
        """
        # Check if the question is empty
        if self.question == "":
            return

        # Add the question to the list of questions.
        qa = QA(question=self.question, answer="")
        self.chats[self.current_chat].append(qa)

        # Clear the input and start the processing.
        self.processing = True
        self.question = ""
        yield

        # # Build the messages.
        # messages = [
        #     {"role": "system", "content": "You are a friendly chatbot named Reflex."}
        # ]
        # for qa in self.chats[self.current_chat]:
        #     messages.append({"role": "user", "content": qa.question})
        #     messages.append({"role": "assistant", "content": qa.answer})

        # # Remove the last mock answer.
        # messages = messages[:-1]

        # Start a new session to answer the question.
        # session = openai.ChatCompletion.create(
        #     model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        #     messages=messages,
        #     stream=True,
        # )

        # Stream the results, yielding after every word.
        # for item in session:
        answer = "I don't know! This Chatbot still needs to add in AI API keys!"
        for i in range(len(answer)):
            # Pause to show the streaming effect.
            await asyncio.sleep(0.1)
            # Add one letter at a time to the output.

            # if hasattr(item.choices[0].delta, "content"):
            #     answer_text = item.choices[0].delta.content
            self.chats[self.current_chat][-1].answer += answer[i]
            self.chats = self.chats
            yield

        # Toggle the processing flag.
        self.processing = False
