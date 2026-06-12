import json
import os

PROFILE_PATH = os.path.join(os.path.dirname(__file__), "user_profile.json")


class UserProfile:
    """Persistent, cross-session info about the user (home location,
    preferences, etc.).

    Stored as a small JSON file. Existing data is loaded on startup, and
    each update is written back to disk immediately, so the profile
    accumulates across runs instead of resetting.
    """

    def __init__(self, path: str = PROFILE_PATH):
        self.path = path
        self.data: dict = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path) as f:
                self.data = json.load(f)
        except (OSError, json.JSONDecodeError):
            self.data = {}

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def get(self, field: str):
        return self.data.get(field)

    def update(self, field: str, value: str) -> dict:
        self.data[field] = value
        self._save()
        return {"saved": field, "value": value}

    def as_prompt_context(self) -> str:
        if not self.data:
            return "No information about the user has been saved yet."
        lines = [f"- {field}: {value}" for field, value in self.data.items()]
        return "Known information about the user:\n" + "\n".join(lines)
