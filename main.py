import json

from agent import WeatherCommuteAgent


def main() -> None:
    agent = WeatherCommuteAgent()
    print("Weather & Commute Assistant (type 'quit' to exit)")
    print("-" * 50)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if user_input.lower() in ("quit", "exit"):
            break
        if not user_input:
            continue

        reply, trace = agent.handle_message(user_input)

        for step in trace:
            if step["type"] == "reasoning":
                print(f"  [reasoning] {step['text']}")
            elif step["type"] == "tool_call":
                print(f"  [tool call] {step['name']}({json.dumps(step['input'])})")
                print(f"  [tool result] {json.dumps(step['result'])}")

        print(f"\nAssistant: {reply}")


if __name__ == "__main__":
    main()
