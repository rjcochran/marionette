from pynput import mouse, keyboard
import threading
import openai
import os
import inspect
import time
import queue
import speech_recognition as sr
import tempfile
openai.api_key = os.getenv("OPENAI_API_KEY")


class ControlScheme(object):
    """
    Orchestrates user interface events and dynamically manages control logic.

    - Converts UI input into a unified, timestamped event stream.
    - Interrupts active control policies upon each new event.
    - Dynamically generates or updates state machine code in response to prompts.
    """
    def __init__(self):
        self.control_policies = []
        self.callbacks = {}
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press)
        self.client = openai.OpenAI(api_key=openai.api_key)
        self.mouse_listener.start()
        self.keyboard_listener.start()

    def on_click(self, x, y, button, pressed):
        event = {
            'type': 'on_click',
            'action': 'press' if pressed else 'release',
            'button': str(button),
            'position': (x, y)
        }
        for control_policy in self.control_policies:
            control_policy.event_queue.put(event)

    def on_key_press(self, key):
        try:
            key_str = key.char
        except AttributeError:
            key_str = str(key)
        event = {
            'type': 'on_key_press',
            'action': 'press',
            'key': key_str
        }
        for control_policy in self.control_policies:
            control_policy.event_queue.put(event)


    def register_callback(self, callback):
        """
        Registers a callback function and stores its docstring.

        Args:
            callback (function): The function to register.
        """
        self.callbacks[callback.__name__] = {'function': callback, 'doc': callback.__doc__}

    def generate_policy_code(self, prompt, model="gpt-4o"):
        """
        Uses the ChatGPT API to generate code for the ControlPolicy.process method
        using the registered callback functions.

        Args:
            prompt (str): A text prompt describing the desired behavior.
            model (str): OpenAI model to use (default: "gpt-5").

        Returns:
            str: The generated Python code as a string.
        """
        if not self.callbacks:
            raise ValueError("No callbacks registered to include in policy generation.")

        # get info
        callback_names = self.callbacks.keys()
        callback_info = "\n".join(f"- {name}: {self.callbacks[cb]['doc']}"
                                  for cb, name in zip(self.callbacks.keys(), callback_names))
        control_policy_source = inspect.getsource(ControlPolicy)

        # generate prompts
        system_prompt = (
            "You are a coding assistant that generates Python code for control policies.\n"
            "Given a set of available callback functions and a behavioral prompt, generate a Python class "
            "that derives from the provided `ControlPolicy` base class.\n"
            "- Only trigger on keyboard / mouse events if explicitly instructed to do so in prompt, otherwise just invoke callbacks directly.\n"
            "- You MUST define the class as a subclass of ControlPolicy using: `class DerivedControlPolicy(ControlPolicy):`\n"            
            "- Output must be raw code only — DO NOT include any quotes, triple quotes, or markdown-style code blocks like ```python.\n"
            "- Include all required imports inline.\n"
            "- When timing is required, implement a `process` method using time.sleep-based delays.\n"
            "- Include a print statement at the top of `process` to confirm execution.\n"
            "- For every callback used, add a print with format: "
            "f'{time.time() - self.start_time:.3f}, func_name(keyword=value)'\n"
            "- Add print statements for every event received on event_queue with format: "
            "f'{time.time() - self.start_time:.3f}, {event dictionary}'\n"
            "- Use only the available callbacks passed into the constructor.\n\n"
            "- Only generate code if there is a high degree of confidence, otherwise return the message 'None'"
            "For reference: "
            f"- ControlPolicy base class: {control_policy_source}\n\n"
            "- Mouse event format: {'type': 'on_click', 'action': 'press' or 'release', 'button': '<Button.left>', 'position': (x, y)}\n\n"
            "- Keyboard event format: {'type': 'on_key_press', 'action': 'press', 'key': '<character or special key>'}\n\n"
        )
        user_prompt = (
            f"The following callbacks are available:\n{callback_info}\n\n"
            f"Write a ControlPolicy.process method that behaves as described:\n{prompt}"
        )

        # generate code
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0
        )
        generated_code = response.choices[0].message.content
        # print(generated_code)

        # exec code
        if generated_code != 'None':
            local_ns = {}
            exec(generated_code, {**globals(), "ControlPolicy": ControlPolicy}, local_ns)
            policy_instance = local_ns["DerivedControlPolicy"](self.callbacks)
            return policy_instance
        else:
            return None

    def add_policy(self, user_prompt, daemon=False):
        try:
            try:
                policy = self.generate_policy_code(user_prompt)
                if policy:
                    for control_policy in self.control_policies:
                        with control_policy.event_queue.mutex:
                            control_policy.event_queue.queue.clear()
                    self.control_policies.append(policy)
                    if daemon:
                        control_thread = threading.Thread(target=policy.process, daemon=True)
                        control_thread.start()
                    else:
                        policy.process()
            except Exception as e:
                print(f"Error generating policy: {e}")
        except KeyboardInterrupt:
            print("Shutting down ControlScheme.")




class ControlPolicy(object):
    """
    Base class for defining time-aware, event-driven control policies.

    - Encapsulates a reactive control state machine with access to a shared event queue.
    - Uses registered callback functions to handle events.
    - Subclasses override the `process` method to define asynchronous control behavior.

    Args:acacac
        callbacks (dict): A dictionary of callback functions and their associated metadata.
    """
    def __init__(self, callbacks):
        self.callbacks = {key: value['function'] for key, value in callbacks.items()}
        self.event_queue = queue.Queue()
        self.start_time = time.time()

    def process(self):
        pass


class SpeechInterface(object):

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.control_scheme = ControlScheme()
        self.client = openai.OpenAI(api_key=openai.api_key)

    def start(self):
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
            print("🎙️ Listening... (Ctrl+C to stop)")
            while True:
                try:
                    audio_data = self.recognizer.listen(source)
                    wav_bytes = audio_data.get_wav_data()
                    with tempfile.NamedTemporaryFile(suffix=".wav") as tf:
                        tf.write(wav_bytes)
                        tf.flush()
                        with open(tf.name, "rb") as f:
                            transcript = self.client.audio.translations.create(model="whisper-1", file=f)
                    prompt = (transcript.text or "").strip()
                    if prompt:
                        print("You said:", prompt)
                        self.control_scheme.add_policy(prompt)
                except sr.WaitTimeoutError:
                    continue
                except KeyboardInterrupt:
                    print("Stopping SpeechInterface.")
                    break
                except Exception as e:
                    print(f"Whisper translation error: {e}")

class TextInterface(object):
    """
    Simple text-based interface that reads typed prompts from stdin and
    forwards them to the ControlScheme to generate and run policies.
    """
    def __init__(self):
        self.control_scheme = ControlScheme()

    def start(self):
        print("⌨️  Type prompts. Press Enter on an empty line to quit. (Ctrl+C to stop)")
        while True:
            try:
                prompt = input("> ").strip()
                if prompt == "":
                    print("Exiting TextInterface.")
                    break
                print("You typed:", prompt)
                self.control_scheme.add_policy(prompt)
            except KeyboardInterrupt:
                print("Stopping TextInterface.")
                break
            except Exception as e:
                print(f"Text input error: {e}")
