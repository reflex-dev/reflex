import reflex as rx
import openai
import traceback
import os
import anthropic

class State(rx.State):

    processing: bool = False
    received: bool = False
    result: str = ""
    prompt: str = ""
    display_models: list[str] = ["Claude 2", "GPT-3.5", "GPT-4"]
    model: str = display_models[0]
    api_model: str = ""
    conversation: list[dict[str, str]] = []

    def reset(self):
        self.processing = False
        self.received = False
        self.result = ""
        self.prompt = ""
        self.api_model = ""
        # self.conversation = rx.vars.ReflexList([])  # Didn't work
        self.conversation = []  # Didn't work

        # self.reset()
    """
    <class 'reflex.vars.ReflexList'>
    Traceback (most recent call last):
    File "/home/user/code/rxtest/venv/lib/python3.11/site-packages/reflex/state.py", line 723, in _process_event
        events = fn(**payload)
                ^^^^^^^^^^^^^
    File "/home/user/code/rxtest/rxtest/rxtest.py", line 27, in reset
        self.reset()
    File "/home/user/code/rxtest/rxtest/rxtest.py", line 27, in reset
        self.reset()
    File "/home/user/code/rxtest/rxtest/rxtest.py", line 27, in reset
        self.reset()
    [Previous line repeated 974 more times]
    File "/home/user/code/rxtest/venv/lib/python3.11/site-packages/reflex/state.py", line 564, in __getattribute__
        if not super().__getattribute__("__dict__"):
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    RecursionError: maximum recursion depth exceeded while calling a Python object
    """

    async def process(self):
        self.processing = True
        self.received = False

    async def run_model(self):
        if self.model == "GPT-4":
            self.api_model = "gpt-4"
        elif self.model == "GPT-3.5":
            self.api_model = "gpt-3.5-turbo-16k"
        elif self.model == "Claude 2":
            self.api_model = "claude-2"
        print(f"Running model: {self.api_model}")

    async def claude(self):
        if self.api_model == "claude-2":
            try:

                client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

                claude_prompt = ""

                self.conversation.append({"role": "user", "content": self.prompt})
                yield

                for message in self.conversation:
                    if message['role'] == "user":
                        claude_prompt += f"{anthropic.HUMAN_PROMPT} {message['content']}"
                    else:
                        claude_prompt += f"{anthropic.AI_PROMPT} {message['content']}"

                claude_prompt += anthropic.AI_PROMPT

                # response = await client.acompletion_stream(
                response = await client.completions.create(
                    prompt=claude_prompt,
                    #stop_sequences = [anthropic.HUMAN_PROMPT],
                    model=self.api_model,
                    max_tokens_to_sample=5000,
                    stream=True,
                )

                self.conversation.append({"role": "assistant", "content": ""})

                async for chunk in response:
                    self.result += chunk.completion
                    self.conversation[-1] = {"role": "assistant", "content": self.result}
                    yield

                print(self.conversation)

                self.prompt = ""
                self.received = True
                self.processing = False
                print(type(self.conversation))

            except Exception as e:
                self.processing = False
                traceback.print_exc()
                print("An error occurred:", e)
                yield rx.window_alert("An error occurred. \n\n" + str(e))


    async def gpt(self):
        try:
            if self.api_model == "gpt-4" or self.api_model == "gpt-3.5-turbo-16k":

                self.conversation.append({"role": "user", "content": self.prompt})
                yield

                print(self.conversation)

                response = openai.ChatCompletion.create(
                    model=self.api_model,
                    messages=self.conversation,
                    temperature=0.5,
                    max_tokens=2000,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0,
                    stream=True,
                )

                # Add blank message to conversation
                self.conversation.append({"role": "assistant", "content": ""})

                collected_chunks = []
                collected_messages = []
                yield

                for chunk in response:
                    collected_chunks.append(chunk)  # save the event response
                    chunk_message = chunk['choices'][0]['delta']  # extract the message
                    collected_messages.append(chunk_message)  # save the message
                    self.result = ''.join([m.get('content', '') for m in collected_messages])
                    self.conversation[-1] = {"role": "assistant", "content": self.result}
                    yield

                full_reply_content = ''.join([m.get('content', '') for m in collected_messages])
                print(f"Full conversation received: {full_reply_content}")

                self.prompt = ""
                self.received = True
                self.processing = False

        except Exception as e:
            self.processing = False
            traceback.print_exc()
            print("An error occurred:", e)
            yield rx.window_alert("An error occurred. \n\n" + str(e))


def index():
    return rx.center(
        rx.vstack(
            rx.heading(
                "Large Language Models",
            ),
            rx.radio_group(
                rx.vstack(
                    rx.foreach(
                        State.display_models,
                        lambda model: rx.box(
                            rx.hstack(
                                rx.radio(model),
                                rx.cond(
                                    model == "GPT-4",
                                    rx.text("More capable than any GPT-3.5 model, able to do more complex tasks. Slower and more expensive than GPT-3.5. Word limit for prompt and response combined is about 6000 words."),
                                ),
                                rx.cond(
                                    model == "GPT-3.5",
                                    rx.text("GPT-3.5 can understand and generate natural language or code. Fast and cheap, but not as capable as GPT-4. Word limit for prompt and response combined is about 12,000 words."),
                                ),
                                rx.cond(
                                    model == "Claude 2",
                                    rx.text("Claude 2 is a large language model (LLM) built by Anthropic. It has a word limit of 75,000 words!"),
                                ),
                                spacing="2em",
                            ),
                            width="40vw",
                        ),
                    ),
                    spacing="2em",
                ),
                default_value=State.display_models[0],
                default_checked=True,
                on_change=State.set_model,
            ),
            rx.foreach(
                State.conversation,
                lambda message: rx.responsive_grid(
                    rx.cond(
                        message["role"] == "assistant",
                        rx.box(
                            rx.markdown(
                                message["content"],
                            ),
                            bg="#D7D7D7",
                            padding="1.0em",
                            width="100%",
                            border_radius="lg",
                        ),
                    ),
                    rx.cond(
                        message["role"] == "user",
                        rx.box(
                            rx.markdown(
                                message["content"],
                            ),
                            bg="white",
                            padding="1.0em",
                            width="100%",
                            border_radius="lg",
                        ),
                    ),
                    columns=[1],
                    width="100%",
                    spacing="1.0em",
                ),
            ),
            rx.text_area(
                on_blur=State.set_prompt,
                id="prompt_id",
                placeholder="Enter your prompt here.",
                width="100%",
                height="20em",
            ),
            rx.cond(
                State.processing,
                rx.button(
                    is_loading=True,
                ),
                rx.button(
                    "Submit Prompt",
                    on_click=[
                        rx.set_value("prompt-id", ""),
                        State.process,
                        State.run_model,
                        State.gpt,
                        State.claude,
                    ],
                ),
            ),
            rx.cond(
                State.processing,
                rx.button(
                    "Reset Chat",
                    is_disabled=True,
                ),
                rx.button(
                    "Reset Chat",
                    on_click=State.reset,
                ),
            ),
            spacing="2em",
        ),
    )


app = rx.App(state=State)
app.add_page(index)
app.compile()
