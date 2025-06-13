from pynput import mouse, keyboard
import time
import simpy

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

