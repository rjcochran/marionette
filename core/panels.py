

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Tree, Static, Input, TextLog
from textual.reactive import reactive
from textual import events

class ControlPolicyUI(App):
    CSS_PATH = "panels.css"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(
                Vertical(Tree("Control Policies", id="tree"), id="left-panel"),
                Vertical(TextLog(id="messages", highlight=True), id="center-panel"),
            ),
            Static("", id="prompt-panel"),
        )
        yield Input(placeholder="Type your prompt and press Enter", id="input")
        yield Footer()

    messages = reactive([])

    def on_mount(self):
        self.query_one("#messages", TextLog).write("System ready. Awaiting policy input...")

    def on_input_submitted(self, message: Input.Submitted):
        prompt = message.value.strip()
        self.query_one("#messages", TextLog).write(f">>> {prompt}")
        self.query_one("#input", Input).value = ""
        # Placeholder: dispatch prompt to backend
        # self.dispatch_prompt(prompt)

    def on_tree_node_selected(self, event: Tree.NodeSelected):
        node = event.node
        self.query_one("#messages", TextLog).write(f"Selected node: {node.label}")

if __name__ == "__main__":
    app = ControlPolicyUI()
    app.run()