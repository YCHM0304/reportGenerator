import click
import requests
import json
import os
import cmd

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

class ReportGeneratorShell(cmd.Cmd):
    """
    報告生成器的命令行界面class。
    繼承自 cmd.Cmd，提供了一個交互式 shell 環境。
    """
    intro = "Welcome to the Report Generator Shell. Type help or ? to list commands.\n"
    prompt = "(report) "

    def do_generate(self, arg):
        """Generate a report: generate <theme> <titles_json> <links> [--openai-key <key>] [--azure-key <key> --azure-base <url>]"""
        args = arg.split()
        if len(args) < 3:
            print("Error: Not enough arguments. Use 'help generate' for usage.")
            return

        theme = args[0]
        titles = args[1]
        links = args[2]
        openai_key = None
        azure_key = None
        azure_base = None

        for i in range(3, len(args)):
            if args[i] == "--openai-key":
                openai_key = args[i+1]
            elif args[i] == "--azure-key":
                azure_key = args[i+1]
            elif args[i] == "--azure-base":
                azure_base = args[i+1]

        try:
            titles_dict = json.loads(titles)
            links_list = links.split(',')
        except json.JSONDecodeError:
            print("Error: Invalid JSON format for titles.")
            return

        data = {
            "theme": theme,
            "titles": titles_dict,
            "links": links_list,
            "openai_config": {}
        }

        if openai_key:
            data["openai_config"]["openai_key"] = openai_key
        if azure_key and azure_base:
            data["openai_config"]["azure_key"] = azure_key
            data["openai_config"]["azure_base"] = azure_base

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
        """Reprocess content: reprocess <command>"""
        if not arg:
            print("Error: Command is required. Use 'help reprocess' for usage.")
            return

        session_id = load_session_id()
        if not session_id:
            print("No active session. Generate a report first.")
            return

        data = {
            "command": arg,
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
        """Exit the Report Generator Shell."""
        print("Goodbye!")
        return True

if __name__ == '__main__':
    ReportGeneratorShell().cmdloop()