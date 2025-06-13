from pynput import mouse, keyboard
import time
import simpy
import openai
import os
openai.api_key = os.getenv("OPENAI_API_KEY")


class ControlScheme(object):
    """
    Orchestrates user interface events and dynamically manages control logic.

    - Converts UI input into a unified, timestamped event stream.
    - Interrupts active control policies upon each new event.
    - Dynamically generates or updates state machine code in response to prompts.
    """
    def __init__(self):
        self.event_stream = []
        self.control_policies = []
        self.callbacks = {}
        self.env = simpy.RealtimeEnvironment()
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.mouse_listener.start()
        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press)
        self.keyboard_listener.start()
        self.client = openai.OpenAI(api_key=openai.api_key)

    def on_click(self, x, y, button, pressed):
        event = {
            'action': 'press' if pressed else 'release',
            'button': str(button),
            'position': (x, y)
        }
        self.process_event(event)

    def on_key_press(self, key):
        try:
            key_str = key.char
        except AttributeError:
            key_str = str(key)
        event = {
            'key': key_str,
            'type': 'press'
        }
        self.process_event(event)

    def process_event(self, event):
        timestamped_event = (event, time.time())
        self.event_stream.append(timestamped_event)
        for policy in self.control_policies:
            policy.interrupt()


    def register_callback(self, callback):
        """
        Registers a callback function and stores its docstring.

        Args:
            callback (function): The function to register.
        """
        self.callbacks[callback] = {'function': callback, 'doc': callback.__doc__}

    def generate_policy_code(self, prompt, model="gpt-4"):
        """
        Uses the ChatGPT API to generate code for the ControlPolicy.process method
        using the registered callback functions.

        Args:
            prompt (str): A text prompt describing the desired behavior.
            model (str): OpenAI model to use (default: "gpt-4").

        Returns:
            str: The generated Python code as a string.
        """
        if not self.callbacks:
            raise ValueError("No callbacks registered to include in policy generation.")

        callback_names = [cb.__name__ for cb in self.callbacks.keys()]
        function_list = "\n".join(f"- {name}: {self.callbacks[cb]['doc'] or 'No docstring'}" for cb, name in zip(self.callbacks.keys(), callback_names))

        system_prompt = (
            "You are a helpful assistant that writes Python coroutine code for simpy-based control policies.\n"
            "Given a set of available callback functions and a behavioral description, generate the body of "
            "a `process` coroutine for a ControlPolicy class. Use appropriate simpy constructs and available callbacks."
        )

        user_prompt = (
            f"The following callbacks are available:\n{function_list}\n\n"
            f"Write a ControlPolicy.process method that behaves as described:\n{prompt}"
        )

        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )

        return response.choices[0].message.content


class ControlPolicy(object):
    """
    Represents a time-aware, interruptible control state machine.

    - Encapsulates simpy-based logic.
    - Registers back-end function handles along with their docstrings.
    - Determines which back-end functions to invoke for each new event.
    """
    def __init__(self, scheme, backend_functions):
        self.env = scheme.env
        self.backend_functions = backend_functions
        scheme.env.process(self.process)

    def process(self):
        while True:
            try:
                yield simpy.Event(self.env)
            except simpy.Interrupt:
                pass
