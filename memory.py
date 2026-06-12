class ConversationMemory:
    """Bounded conversation history for the agent's context window.

    Messages are grouped into "turns" (one user request, plus any
    tool-use/tool-result exchanges, plus the final assistant reply).
    Trimming only ever drops whole turns, so a tool_use block is never
    separated from its matching tool_result.
    """

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self.turns: list[list[dict]] = []
        self.current_turn: list[dict] = []

    def start_turn(self, user_message: dict) -> None:
        self.current_turn = [user_message]

    def add_to_current_turn(self, message: dict) -> None:
        self.current_turn.append(message)

    def end_turn(self) -> None:
        self.turns.append(self.current_turn)
        self.current_turn = []
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def get_messages(self) -> list[dict]:
        messages: list[dict] = []
        for turn in self.turns:
            messages.extend(turn)
        messages.extend(self.current_turn)
        return messages
