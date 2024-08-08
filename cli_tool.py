import inquirer
import requests
import json
import os
import cmd
import time

API_BASE_URL = "http://127.0.0.1:8000"
SESSION_FILE = ".session_id"

def load_session_id():
    """
    從文件中載入會話 ID。
    如果文件存在，讀取並返回其內容；否則返回 None。
    """
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            return f.read().strip()
    return None

def save_session_id(session_id):
    """
    將會話 ID 保存到文件中。
    """
    with open(SESSION_FILE, "w") as f:
        f.write(session_id)

def delete_session_id():
    """
    刪除保存的會話 ID 文件。
    """
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)

class ReportGeneratorShell(cmd.Cmd):
    """
    報告生成器的命令行界面class。
    繼承自 cmd.Cmd，提供了一個交互式 shell 環境。
    """
    intro = "Welcome to the Report Generator Shell. Select a function to execute.\n"
    prompt = "(report) "

    def __init__(self):
        super().__init__()
        self.setup_api()

    def setup_api(self):
        questions = [
            inquirer.List(
                "api", message="Select the API to use", choices=["OpenAI", "Azure"], default="OpenAI"
            )
        ]
        type = inquirer.prompt(questions)
        if type["api"] == "OpenAI":
            questions = [
                inquirer.Password(
                    "openai_key", message="Enter your OpenAI key"
                )
            ]
        elif type["api"] == "Azure":
            questions = [
                inquirer.Password(
                    "azure_key", message="Enter your Azure key"
                ),
                inquirer.Text(
                    "azure_base", message="Enter your Azure base URL"
                ),
            ]
        answers = inquirer.prompt(questions)
        if type["api"] == "OpenAI":
            self.openai_key = answers.get("openai_key")
            self.azure_key = self.azure_base = None
        else:
            self.openai_key = None
            self.azure_key = answers.get("azure_key")
            self.azure_base = answers.get("azure_base")

    def choose_function(self):
        print()
        questions = [
            inquirer.List(
                "function",
                message="Choose a function to execute",
                choices=[
                    ("Generate Report", "generate"),
                    ("Check Report Status", "check"),
                    ("Get Report", "get"),
                    ("Reprocess Content", "reprocess"),
                    ("Help", "help"),
                    ("Prompt", "prompt"),
                    ("Exit", "exit")
                ]
            )
        ]
        answer = inquirer.prompt(questions)
        return answer['function']

    def cmdloop(self, intro=None):
        print("\n" + self.intro)
        while True:
            choice = self.choose_function()
            if choice == 'generate':
                self.do_generate('')
            elif choice == 'check':
                self.do_check('')
                time.sleep(3)
            elif choice == 'get':
                self.do_get('')
                time.sleep(3)
            elif choice == 'reprocess':
                self.do_reprocess(input("Enter command for reprocess: "))
            elif choice == 'help':
                questions = [
                    inquirer.List(
                        "help_option",
                        message="Choose a function to get help on",
                        choices=[
                            ("Generate Report", "generate"),
                            ("Check Report Status", "check"),
                            ("Get Report", "get"),
                            ("Reprocess Content", "reprocess"),
                        ]
                    )
                ]
                answer = inquirer.prompt(questions)
                self.do_help(answer["help_option"])
                time.sleep(3)
            elif choice == 'prompt':
                self.prompt_mode()
            elif choice == 'exit':
                self.do_exit('')
                break

    def prompt_mode(self):
        print("Entering command prompt mode. Type 'exit' to return to the main menu.")
        while True:
            try:
                line = input(self.prompt)
                if line == 'exit':
                    print("Returning to main menu...")
                    break
                else:
                    self.onecmd(line)
            except EOFError:
                print("Exiting command prompt mode...")
                break

    def do_generate(self, arg):
        """
        Generate a report: generate <theme> <titles_json> <links>
        <theme>: The theme of the report.
        <titles_json>: A JSON object with titles and their corresponding content.
        <links>: A comma-separated list of links to include in the report.
        """
        theme = inquirer.text(message="Enter the theme of the report")
        if not theme:
            print("Error: Theme is required. Use 'help generate' for usage.")
            return

        i = 1
        titles_dict = {}
        while True:
            si = 1
            t = inquirer.text(message=f"Enter the {i} title")
            if t == 'end':
                break
            tmp_title = []
            while True:
                st = inquirer.text(message=f"Enter the {si} subtitle of the {i} title")
                if st == 'end':
                    break
                tmp_title.append(st)
                si += 1
            titles_dict[t] = tmp_title
            i += 1

        if not titles_dict:
            print("Error: At least one title is required. Use 'help generate' for usage.")
            return

        i = 1
        links_list = []
        while True:
            l = inquirer.text(message=f"Enter the {i} link separated by commas")
            if l == 'end':
                break
            links_list.append(l)
            i += 1

        if not links_list:
            print("Error: At least one link is required. Use 'help generate' for usage.")
            return

        data = {
            "theme": theme,
            "titles": titles_dict,
            "links": links_list,
            "openai_config": {}
        }
        if self.openai_key:
            data["openai_config"]["openai_key"] = self.openai_key
        if self.azure_key and self.azure_base:
            data["openai_config"]["azure_key"] = self.azure_key
            data["openai_config"]["azure_base"] = self.azure_base

        print(data)
        session_id = load_session_id()
        headers = {"session_id": session_id} if session_id else {}

        response = requests.post(f"{API_BASE_URL}/generate_report", json=data, headers=headers, verify=False)
        if response.status_code == 200:
            result = response.json()
            save_session_id(result["session_id"])
            print(f"Report generated successfully. Session ID: {result['session_id']}")
        else:
            print(f"Error: {response.status_code} - {response.text}")

    def do_check(self, arg):
        """Check if a report has been generated."""
        session_id = load_session_id()
        if not session_id:
            print("No active session. Generate a report first.")
            return

        response = requests.get(f"{API_BASE_URL}/check_result", headers={"session_id": session_id})
        if response.status_code == 200:
            result = response.json()
            print(f"Result available: {result['result']}")
        else:
            print(f"Error: {response.status_code} - {response.text}")

    def do_get(self, arg):
        """Get the generated report."""
        session_id = load_session_id()
        if not session_id:
            print("No active session. Generate a report first.")
            return

        response = requests.get(f"{API_BASE_URL}/get_report", headers={"session_id": session_id})
        if response.status_code == 200:
            result = response.json()
            print(json.dumps(result["result"], ensure_ascii=False, indent=2))
        else:
            print(f"Error: {response.status_code} - {response.text}")

    def do_reprocess(self, arg):
        """
        Reprocess content: reprocess <command>
        <command>: The command to reprocess.
        """

        command = inquirer.text(message="Enter the command for reprocess")
        if not command:
            print("Error: Command is required. Use 'help reprocess' for usage.")
            return

        session_id = load_session_id()
        if not session_id:
            print("No active session. Generate a report first.")
            return

        data = {
            "command": command,
            "openai_config": {}  # Add OpenAI config if needed
        }

        response = requests.post(f"{API_BASE_URL}/reprocess_content", json=data, headers={"session_id": session_id})
        if response.status_code == 200:
            result = response.json()
            print("Content reprocessed successfully:")
            print(f"Part: {result['result']['part']}")
            print("Original content:")
            print(result['result']['original_content'])
            print("Modified content:")
            print(result['result']['modified_content'])
        else:
            print(f"Error: {response.status_code} - {response.text}")

    def do_exit(self, arg):
        """Delete user session and exit the Report Generator Shell."""
        if os.path.exists(SESSION_FILE):
            session_id = load_session_id()
            requests.delete(f"{API_BASE_URL}/delete_session", headers={"session_id": session_id})
            delete_session_id()
            print("Session deleted.")
        print("Goodbye!")
        return True

if __name__ == '__main__':
    ReportGeneratorShell().cmdloop()