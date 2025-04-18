from google import genai
from google.genai import types
import os
import sys
from pathlib import Path
import traceback
# Placeholder imports for tool functions (to be implemented in tools.py)
from tools import read_file, list_files, edit_file, execute_bash_command, run_in_sandbox

# Choose your Gemini model
MODEL_NAME = "gemini-2.0-flash"

# Define project root
project_root = Path(__file__).resolve().parent


class CodeAgent:
    """A simple coding agent using Google Gemini (google-genai SDK)."""

    def __init__(self, api_key: str, model_name: str = MODEL_NAME):
        self.api_key = api_key
        self.model_name = f'models/{model_name}'
        self.tool_functions = [
            read_file,
            list_files,
            edit_file,
            execute_bash_command,
            run_in_sandbox
        ]
        self.client = None
        self.chat = None
        self.conversation_history = []  # Manual history for token counting ONLY
        self.current_token_count = 0  # Store token count for the next prompt
        self._configure_client()

    def _configure_client(self):
        print("\n⚒️ Configuring genai client...")
        try:
            self.client = genai.Client(api_key=self.api_key)
            print("✅ Client configured successfully.")
        except Exception as e:
            print(f"❌ Error configuring genai client: {e}")
            traceback.print_exc()
            sys.exit(1)

    def start_interaction(self):
        if not self.client:
            print("\n❌ Client not configured. Exiting.")
            return
        print("\n⚒️ Initializing chat session...")
        try:
            self.chat = self.client.chats.create(
                model=self.model_name, history=[])
            print("✅ Chat session initialized.")
        except Exception as e:
            print(f"❌ Error initializing chat session: {e}")
            traceback.print_exc()
            sys.exit(1)
        print("\n⚒️ Agent ready. Ask me anything. Type 'exit' to quit.")
        tool_config = types.GenerateContentConfig(tools=self.tool_functions)
        while True:
            try:
                prompt_text = f"\n🔵 You ({self.current_token_count}): "
                user_input = input(prompt_text).strip()
                if user_input.lower() in ["exit", "quit"]:
                    print("\n👋 Goodbye!")
                    break
                if not user_input:
                    continue
                # Add user message to manual history BEFORE sending
                new_user_content = types.Content(
                    parts=[types.Part(text=user_input)], role="user")
                self.conversation_history.append(new_user_content)
                print("\n⏳ Sending message and processing...")
                response = self.chat.send_message(
                    message=user_input,
                    config=tool_config
                )
                # Add agent response to manual history AFTER getting it
                agent_response_content = None
                if response.candidates and response.candidates[0].content:
                    agent_response_content = response.candidates[0].content
                    self.conversation_history.append(agent_response_content)
                else:
                    print(
                        "\n⚠️ Agent response did not contain content for history/counting.")
                print(f"\n🟢 \x1b[92mAgent:\x1b[0m {response.text}")
                # Calculate and store token count for the next prompt
                try:
                    token_count_response = self.client.models.count_tokens(
                        model=self.model_name,
                        contents=self.conversation_history
                    )
                    self.current_token_count = token_count_response.total_tokens
                except Exception as count_error:
                    print(f"\n⚠️ Could not update token count: {count_error}")
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n🔴 An error occurred during interaction: {e}")
                traceback.print_exc()


if __name__ == "__main__":
    print("🚀 Starting Code Agent...")
    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        print("❌ GOOGLE_API_KEY environment variable not set.")
        sys.exit(1)
    agent = CodeAgent(api_key=api_key, model_name=MODEL_NAME)
    agent.start_interaction()
