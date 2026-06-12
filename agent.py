import json
from datetime import date

import anthropic

from config import ANTHROPIC_API_KEY, MODEL_NAME
from memory import ConversationMemory
from profile import UserProfile
from tools import news, packing, weather

# Safety cap on tool-calling rounds per user message, so a confused model
# can't loop indefinitely and rack up API calls.
MAX_TOOL_ITERATIONS = 6

TOOLS = [
    {
        "name": "resolve_location",
        "description": (
            "Check whether a location name unambiguously identifies a single "
            "place, and get its canonical 'City, State, Country' form. Use "
            "this before saving a location to the user's profile (e.g. "
            "home_location/work_location) via update_user_profile, since "
            "names like 'Springfield' match multiple cities. If it returns "
            "an 'ambiguous_location' error with candidate matches, ask the "
            "user which one they mean before saving anything."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name, e.g. 'Springfield'"},
            },
            "required": ["location"],
        },
    },
    {
        "name": "get_weather",
        "description": (
            "Get the weather forecast for a location. Forecasts are only "
            "available for roughly the next 5 days. If the location name is "
            "shared by other places (e.g. 'San Diego' also exists in Texas), "
            "this proceeds with the most likely match and includes a "
            "'possible_alternates' list - mention the assumption in your "
            "response so the user can correct it if needed. If the location "
            "can't be found at all, returns an 'error'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name, e.g. 'Seattle'"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "end_date": {
                    "type": "string",
                    "description": (
                        "Optional end date (YYYY-MM-DD, inclusive) for a multi-day "
                        "forecast. If given, returns a per-day breakdown from "
                        "`date` to `end_date` instead of a single summary. Omit "
                        "for a single-day request."
                    ),
                },
            },
            "required": ["location", "date"],
        },
    },
    {
        "name": "get_weather_news",
        "description": (
            "Search recent news for weather-related advisories, storms, or "
            "travel disruptions affecting a location. Most useful for travel "
            "requests. Pass the weather condition from get_weather - if it "
            "isn't severe enough to cause disruptions, this tool will skip "
            "the search and say so. Each headline includes 'days_ago' "
            "(how many days ago it was published) - use this to judge "
            "whether a headline still reflects current conditions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City or region name"},
                "condition": {
                    "type": "string",
                    "description": "The weather condition for that location/date, as returned by get_weather (e.g. 'Rain', 'Clear', 'Snow')",
                },
            },
            "required": ["location", "condition"],
        },
    },
    {
        "name": "get_packing_recommendation",
        "description": (
            "Get a list of recommended items to bring based on the weather "
            "condition, the activity type, and (optionally) the temperature range."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "condition": {
                    "type": "string",
                    "description": "Weather condition, e.g. 'Rain', 'Clear', 'Snow'",
                },
                "activity_type": {
                    "type": "string",
                    "enum": ["commute", "outdoor_activity", "travel", "general"],
                    "description": "Type of activity the user is preparing for",
                },
                "temp_max": {
                    "type": "number",
                    "description": "Maximum expected temperature in Fahrenheit",
                },
                "temp_min": {
                    "type": "number",
                    "description": "Minimum expected temperature in Fahrenheit",
                },
            },
            "required": ["condition", "activity_type"],
        },
    },
    {
        "name": "update_user_profile",
        "description": (
            "Save a persistent fact about the user for future sessions. Use "
            "this when the user states a lasting preference (e.g. 'I live in "
            "Seattle'), or when they answer a clarifying question and that "
            "answer represents a recurring default (e.g. their home base)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "enum": ["home_location", "work_location", "units"],
                    "description": "Which piece of user information to save",
                },
                "value": {"type": "string", "description": "The value to save"},
            },
            "required": ["field", "value"],
        },
    },
]


def build_system_prompt(profile_context: str) -> str:
    today = date.today().isoformat()
    return f"""You are a Weather & Commute Assistant. Today's date is {today}.

{profile_context}

Your job is to help users prepare for their day by understanding their plans,
checking the weather (and travel news if relevant), and giving practical,
actionable recommendations.

Scope: only help with weather, commuting, travel preparation, and what to
wear/bring for an activity. If a request is unrelated (e.g. general trivia,
coding help, creative writing), politely explain that this is outside what
you can help with and do not call any tools.

For each user request:
1. Identify the location, date/time, and activity type. Classify the activity
   as one of: commute, outdoor_activity, travel, or general.
2. If the location is missing or too vague:
   - If a home_location is known (see above), use it as the default, but say
     so explicitly (e.g. "I'll check San Francisco, your usual location...")
     so the user can correct you if they meant somewhere else.
   - If no home_location is known, ask the user where they need this for. If
     their answer represents a recurring default (e.g. their home base),
     also call update_user_profile to save it so you don't have to ask again.
   - Before saving any location to the profile via update_user_profile
     (home_location/work_location), call resolve_location first. If it
     returns an "ambiguous_location" error, do NOT save anything yet -
     instead ask the user which specific place they mean (listing the
     candidates), then save the canonical resolved form once they clarify.
3. If the date/time is missing or too vague to proceed, ask a clarifying question.
4. Resolve relative dates (e.g. "tomorrow", "next Saturday") against today's date.
5. Use get_weather to check conditions for the relevant date(s). If the
   request spans multiple days (e.g. a trip from Friday to Sunday), pass
   both `date` (the first day) and `end_date` (the last day) in a single
   call rather than calling get_weather once per day.
6. For travel-related requests, after checking the weather, also call
   get_weather_news with that location and the weather condition you just
   found (for multi-day results, use the most severe condition across the
   days). This tool will automatically skip the news search if the
   condition isn't severe enough to cause disruptions.
7. If get_weather_news returns headlines, reconcile them with the forecast
   using this priority order:
   - The live forecast from get_weather is authoritative for what the
     weather itself will be - lead with that.
   - Recent headlines (days_ago of roughly 0-2, or otherwise covering the
     trip's timeframe) supplement the forecast with operational disruptions
     (delays, closures, cancellations) that can persist even after the
     weather clears. Don't dismiss a relevant headline just because the
     forecast looks clear - frame it as e.g. "the forecast looks clear, but
     there may still be lingering delays from earlier storms."
   - If multiple recent headlines disagree with each other, don't silently
     pick one - briefly surface that reports are mixed and suggest the user
     double-check before relying on it.
   - Headlines with a large days_ago (more than ~2-3 days, and not clearly
     about the trip's dates) are likely stale - omit them, or mention them
     only as brief background, not as something currently affecting the trip.
8. Use get_packing_recommendation to determine what to bring, based on the
   weather condition, activity type, and temperature range. For multi-day
   results, base this on the day(s) with the most severe conditions, or
   call it once per day if the conditions vary significantly.
9. If a tool returns an error, explain the limitation to the user and give
   general advice where possible instead of failing silently:
   - If get_weather returns a "possible_alternates" list, briefly note which
     place you used (e.g. "I'll check San Diego, CA") so the user can
     correct you if they meant one of the alternates - but otherwise proceed
     normally, don't block on it.
   - For errors (service unavailable, location not found, date out of
     forecast range, etc.), explain the limitation and give general advice
     where possible.
10. Summarize everything into a concise, actionable recommendation that
    mentions the temperature, conditions, what to bring, and any relevant
    advisories.
"""


class WeatherCommuteAgent:
    def __init__(self, max_turns: int = 10):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.memory = ConversationMemory(max_turns=max_turns)
        self.profile = UserProfile()
        self.tool_functions = {
            "resolve_location": weather.resolve_location,
            "get_weather": weather.get_weather,
            "get_weather_news": news.get_weather_news,
            "get_packing_recommendation": packing.get_packing_recommendation,
            "update_user_profile": self.profile.update,
        }

    def handle_message(self, user_input: str) -> tuple[str, list[dict]]:
        """Process one user message and return (reply_text, trace).

        `trace` is a list of steps the agent took before producing the
        final reply - each is either {"type": "reasoning", "text": ...}
        (narration the model produced before calling a tool) or
        {"type": "tool_call", "name", "input", "result"}.
        """
        self.memory.start_turn({"role": "user", "content": user_input})
        trace: list[dict] = []

        for _ in range(MAX_TOOL_ITERATIONS):
            try:
                response = self.client.messages.create(
                    model=MODEL_NAME,
                    max_tokens=1024,
                    system=build_system_prompt(self.profile.as_prompt_context()),
                    messages=self.memory.get_messages(),
                    tools=TOOLS,
                )
            except anthropic.APIError as exc:
                self.memory.end_turn()
                return (
                    "Sorry, I'm having trouble reaching the assistant service "
                    f"right now ({exc.__class__.__name__}). Please try again "
                    "in a moment.",
                    trace,
                )

            self.memory.add_to_current_turn({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                self.memory.end_turn()
                final_text = "".join(block.text for block in response.content if block.type == "text")
                return final_text, trace

            # Narration the model produced before deciding to call tool(s)
            for block in response.content:
                if block.type == "text" and block.text.strip():
                    trace.append({"type": "reasoning", "text": block.text})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._execute_tool(block.name, block.input)
                    trace.append(
                        {"type": "tool_call", "name": block.name, "input": block.input, "result": result}
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        }
                    )

            self.memory.add_to_current_turn({"role": "user", "content": tool_results})

        self.memory.end_turn()
        return (
            "I'm having trouble completing this request after several steps. "
            "Could you try rephrasing or simplifying your question?",
            trace,
        )

    def _execute_tool(self, name: str, tool_input: dict) -> dict:
        try:
            return self.tool_functions[name](**tool_input)
        except Exception as exc:
            return {"error": f"Tool execution failed: {exc}"}
