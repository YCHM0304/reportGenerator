import streamlit as st
import requests
import time
import json
import os

if not os.environ.get("API_BASE_URL"):
    API_BASE_URL = "http://127.0.0.1:8000"
else:
    API_BASE_URL = os.environ["API_BASE_URL"]

def get_access_token():
    """
    從 Streamlit 的 session_state 中獲取存儲的訪問令牌。
    如果沒有找到令牌，則返回 None。
    """
    return st.session_state.get('access_token', None)

def set_access_token(token):
    """
    將提供的訪問令牌存儲在 Streamlit 的 session_state 中。

    參數:
    token (str): 要存儲的訪問令牌
    """
    st.session_state['access_token'] = token

def clear_access_token():
    """
    從 Streamlit 的 session_state 中刪除存儲的訪問令牌。
    如果令牌不存在，則不執行任何操作。
    """
    if 'access_token' in st.session_state:
        del st.session_state['access_token']

def initialize_session_state():
    """
    初始化所有需要的 session state 變量。
    """
    if 'api_config' not in st.session_state:
        st.session_state.api_config = {
            'api_type': 'OpenAI',
            'openai_key': '',
            'azure_key': '',
            'azure_base': ''
        }

    if 'generate_report_clicked' not in st.session_state:
        st.session_state.generate_report_clicked = False
        st.session_state.reprocess_report_clicked = False
    if 'reprocess_command' not in st.session_state:
        st.session_state.reprocess_command = ""
    if 'reprocess_result' not in st.session_state:
        st.session_state.reprocess_result = None
    if 'reprocess_clicked' not in st.session_state:
        st.session_state.reprocess_clicked = False
    if 'generate_recommend_main_sections_clicked' not in st.session_state:
        st.session_state.generate_recommend_main_sections_clicked = False

def setup_api():
    """
    在側邊欄中創建 API 設置界面，允許用戶選擇 API 類型（OpenAI 或 Azure）
    並輸入相應的 API 密鑰和（如果適用）基礎 URL。

    返回:
    dict: 包含用戶輸入的 API 配置信息
    """
    initialize_session_state()

    api_type = st.sidebar.selectbox(
        "Select the API to use",
        ["OpenAI", "Azure"],
        key="api_type",
        index=0 if st.session_state.api_config['api_type'] == 'OpenAI' else 1
    )

    if api_type == "OpenAI":
        openai_key = st.sidebar.text_input(
            "Enter your OpenAI key",
            type="password",
            value=st.session_state.api_config['openai_key']
        )
        st.session_state.api_config.update({
            'api_type': 'OpenAI',
            'openai_key': openai_key
        })
        return {"openai_key": openai_key}
    else:
        azure_key = st.sidebar.text_input(
            "Enter your Azure key",
            type="password",
            value=st.session_state.api_config['azure_key']
        )
        azure_base = st.sidebar.text_input(
            "Enter your Azure base URL",
            value=st.session_state.api_config['azure_base']
        )
        st.session_state.api_config.update({
            'api_type': 'Azure',
            'azure_key': azure_key,
            'azure_base': azure_base
        })
        return {"azure_key": azure_key, "azure_base": azure_base}

def clear_api_config():
    """
    清除存儲在 session state 中的 API 配置。
    """
    st.session_state.api_config = {
        'api_type': 'OpenAI',
        'openai_key': '',
        'azure_key': '',
        'azure_base': ''
    }

def register_user():
    """
    創建用戶註冊界面，允許新用戶註冊賬戶。
    處理註冊請求並在成功時設置訪問令牌。
    """
    st.header("User Registration")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")
    if st.button("Register"):
        if password == confirm_password:
            response = requests.post(f"{API_BASE_URL}/register", json={"username": username, "password": password})
            if response.status_code == 200:
                token = response.json()["access_token"]
                set_access_token(token)
                st.success("Registration successful. You are now logged in.")
                time.sleep(3)
                st.rerun()
            else:
                st.error(f"Registration failed: {response.text}")
        else:
            st.error("Passwords do not match.")

def login_user():
    """
    創建用戶登錄界面，允許現有用戶登錄。
    處理登錄請求並在成功時設置訪問令牌。
    """
    st.header("User Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        response = requests.post(f"{API_BASE_URL}/token", data={"username": username, "password": password})
        if response.status_code == 200:
            token = response.json()["access_token"]
            set_access_token(token)
            st.success("Login successful.")
            st.rerun()
        else:
            st.error(f"Login failed: {response.text}")

def generate_recommend_main_sections(api_config, report_topic):
    data = {
        "report_topic": report_topic,
        "main_sections": {},
        "links": [],
        "openai_config": api_config
    }

    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}

    with st.spinner("Generating recommended main sections..."):
        response = requests.post(f"{API_BASE_URL}/generate_recommend_main_sections", json=data, headers=headers)
        if response.status_code == 200:
            result = response.json()
            st.success("Recommended main sections generated successfully.")
            try:
                main_sections = json.loads(result["result"])
                if isinstance(main_sections, dict) and "主要部分" in main_sections and "次要部分" in main_sections:
                    return main_sections
                else:
                    st.error("Received data is not in the expected format.")
                    return None
            except json.JSONDecodeError:
                st.error("Failed to parse the received data.")
                return None
        else:
            st.error(f"Error: {response.status_code} - {response.text}")
            return None

def reset_states():
    """
    重置所有相關的 session_state 變量到其初始狀態。
    這用於清理和重置應用程序的狀態。
    """
    st.session_state.current_page = 'generate_and_reprocess_report'
    st.session_state.generate_report_clicked = False
    st.session_state.reprocess_report_clicked = False
    st.session_state.recommended_main_sections = None
    st.session_state.reprocess_clicked = False
    st.session_state.reprocess_command = ""
    st.session_state.reprocess_result = None
    st.session_state.report_topic = ""
    st.session_state.num_main_sections = 1
    st.session_state.main_sections_dict = {}
    st.session_state.links = ""
    st.session_state.generate_recommend_main_sections_clicked = False

def generate_report(api_config):
    st.header("Generate Report")

    report_topic = st.text_input("Enter the report topic")

    if 'recommended_main_sections' not in st.session_state:
        st.session_state.recommended_main_sections = None

    if 'num_main_sections' not in st.session_state:
        st.session_state.num_main_sections = 1

    col1, col2 = st.columns(2)
    with col1:
        generate_recommend_main_sections_clicked = st.button("Generate Recommended Main Sections", disabled=st.session_state.generate_recommend_main_sections_clicked or st.session_state.generate_report_clicked or st.session_state.reprocess_clicked, help="Generate recommended main sections based on the report topic.")

    with col2:
        if st.button("Reset Main Sections", disabled=st.session_state.generate_recommend_main_sections_clicked):
            st.session_state.recommended_main_sections = None
            st.session_state.num_main_sections = 1

    if generate_recommend_main_sections_clicked:
            st.session_state.generate_recommend_main_sections_clicked = True
            st.rerun()
    if st.session_state.generate_recommend_main_sections_clicked:
        if report_topic:
            st.session_state.recommended_main_sections = generate_recommend_main_sections(api_config, report_topic)
            if st.session_state.recommended_main_sections:
                    st.session_state.num_main_sections = len(st.session_state.recommended_main_sections["主要部分"])
        else:
            st.error("Please enter a report topic before generating main sections.")
        time.sleep(3)
        st.session_state.generate_recommend_main_sections_clicked = False
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Add Main Section"):
            st.session_state.num_main_sections += 1
    with col2:
        if st.button("Remove Main Section") and st.session_state.num_main_sections > 1:
            st.session_state.num_main_sections -= 1

    main_sections_dict = {}

    st.info("""
        **Main Sections and Subsections Guide:**

        - **Main Sections**: Primary topics or chapters of your report. Each main section represents a major part of your content.

        - **Subsections**: Specific points or subtopics under each main section. Enter each subsection on a new line.

        Example:

        Main Section: "Introduction to AI"

        Subsections:

        - Definition of AI

        - Brief history of AI

        - Current applications of AI

        **Be sure to fill in all fields before generating the report.**
        """)

    for i in range(st.session_state.num_main_sections):
        col1, col2 = st.columns(2)
        with col1:
            main_section_key = f"main_section_{i}"
            default_main_section = ""
            if st.session_state.recommended_main_sections and i < len(st.session_state.recommended_main_sections["主要部分"]):
                default_main_section = st.session_state.recommended_main_sections["主要部分"][i]
            main_section = st.text_input(f"Main Section {i+1}", key=main_section_key, value=default_main_section)
        with col2:
            subsections_key = f"subsections_{i}"
            default_subsections = ""
            if st.session_state.recommended_main_sections and i < len(st.session_state.recommended_main_sections["次要部分"]):
                default_subsections = "\n".join(st.session_state.recommended_main_sections["次要部分"][i])
            subsections = st.text_area(f"Subsections for Main Section {i+1} (one per line)", key=subsections_key, value=default_subsections)
        if main_section and subsections:
            main_sections_dict[main_section] = subsections.split('\n')

    links = st.text_area("Enter links (one per line)")
    links_list = links.split('\n') if links else []
    final_summary = st.checkbox("Generate final summary", value=True, help="Generate an extra final summary based on the generated contents.")
    col1, col2 = st.columns(2)
    with col1:
        generate_report_clicked = st.button("Generate Report", key="generate_report", disabled=st.session_state.generate_report_clicked or st.session_state.reprocess_clicked, use_container_width=True)
    with col2:
        reset = st.button("Reset All", key="reset_all", use_container_width=True, disabled=st.session_state.generate_report_clicked or st.session_state.reprocess_clicked)

    if generate_report_clicked:
        if not report_topic or not main_sections_dict or not links_list:
            st.error("Please fill in all fields.")
            return
        st.session_state.generate_report_clicked = True
        st.rerun()
    if reset:
        reset_states()
        st.session_state.recommended_main_sections = None
        st.rerun()

    if st.session_state.generate_report_clicked:
        data = {
            "report_topic": report_topic,
            "main_sections": main_sections_dict,
            "links": links_list,
            "openai_config": api_config,
            "final_summary": final_summary
        }

        access_token = get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}

        with st.spinner("Generating report..."):
            response = requests.post(f"{API_BASE_URL}/generate_report", json=data, headers=headers, verify=False)
            if response.status_code == 200:
                result = response.json()
                st.success(f"Report generated successfully. Total time: {result['total_time']} seconds.")
            else:
                st.error(f"Error: {response.status_code} - {response.text}")

        time.sleep(3)
        st.session_state.generate_report_clicked = False
        st.session_state.report_checked = False
        st.rerun()

def get_report():
    """
    創建獲取報告界面，允許用戶獲取之前生成的報告。
    處理獲取報告請求並顯示結果。
    """
    st.session_state.current_page = 'get_report'
    st.header("Get Report")

    access_token = get_access_token()
    if not access_token:
        st.warning("Please login first.")
        return

    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    response = requests.get(f"{API_BASE_URL}/get_report", headers=headers)
    if response.status_code == 200:
        result = response.json()
        st.json(result["result"])
        # Add download button
        download_report(headers)
    else:
        st.error(f"Error: {response.status_code} - {response.text}")

def reprocess_content(api_config):
    """
    創建重新處理內容界面，允許用戶輸入命令來重新處理之前生成的報告內容。
    處理重新處理請求並顯示結果。提供選項保存修改後的內容。
    保留按鈕鎖定功能。
    """
    st.header("Reprocess Content")

    access_token = get_access_token()
    if not access_token:
        st.warning("Please login first.")
        return

    st.info("""
        Only **one main section** of the content can be reprocessed at a time.
        Request more than one main section will result in an error.
    """)
    command = st.text_input("Enter the command for reprocess", value=st.session_state.reprocess_command)
    more_info_from_links = st.checkbox("Additional Information Source URLs", value=False, help='Add more URLs to expand the data sources for your report.')
    if more_info_from_links:
        links = st.text_area("Enter links (one per line)", key=more_info_from_links)
        links_list = links.split('\n') if links else []

    col1, col2 = st.columns(2)
    with col1:
        reprocess_button = st.button("Reprocess Report", disabled=st.session_state.reprocess_clicked or st.session_state.generate_report_clicked, use_container_width=True)
    with col2:
        reset_button = st.button("Reset", use_container_width=True, disabled=st.session_state.reprocess_clicked or st.session_state.generate_report_clicked)

    if reprocess_button:
        if not command:
            st.error("Command is required.")
            return
        st.session_state.reprocess_clicked = True
        st.rerun()

    if reset_button:
        reset_states()
        st.rerun()

    if st.session_state.reprocess_clicked:
        st.session_state.reprocess_clicked = True
        st.session_state.reprocess_command = command
        data = {
            "command": command,
            "openai_config": api_config,
            "links": links_list if more_info_from_links else None
        }

        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        with st.spinner("Reprocessing report..."):
            response = requests.post(f"{API_BASE_URL}/reprocess_content", json=data, headers=headers)
            if response.status_code == 422 and "requires_user_input" in response.json().get("detail", {}):
                # 處理"unknown"
                detail = response.json()["detail"]
                st.warning(detail["message"])
                user_decision = st.radio(
                    detail["input_question"],
                    options=["Yes", "No"],
                    key="user_decision"
                )

                if st.button("Submit"):
                    user_decision_bool = user_decision == "Yes"
                    data["user_decision"] = user_decision_bool
                    response = requests.post(f"{API_BASE_URL}/reprocess_content", json=data, headers=headers)

                    if response.status_code == 200:
                        st.session_state.reprocess_result = response.json()['result']
                        st.success("Content reprocessed successfully.")
                    else:
                        st.error(f"Error: {response.status_code} - {response.text}")
                        st.session_state.reprocess_result = None

            elif response.status_code == 200:
                st.session_state.reprocess_result = response.json()['result']
                st.success("Content reprocessed successfully.")
            else:
                st.error(f"Error: {response.status_code} - {response.text}")
                st.session_state.reprocess_result = None

        time.sleep(3)
        st.session_state.reprocess_clicked = False
        st.rerun()

    if st.session_state.reprocess_result:
        result = st.session_state.reprocess_result
        st.write(f"Main Section: {result['main_section']}")
        st.subheader("Original content:")
        st.write(result['original_content'])
        st.subheader("Modified content:")
        st.write(result['modified_content'])

        if st.button("Save Changes"):
            save_data = {
                "main_section": result['main_section'],
                "new_content": result['modified_content']
            }
            headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
            save_response = requests.post(f"{API_BASE_URL}/save_reprocessed_content", json=save_data, headers=headers)
            if save_response.status_code == 200:
                st.success("Changes saved successfully.")
                # 重置狀態，為下一次重新處理做準備
                st.session_state.reprocess_result = None
                st.session_state.reprocess_clicked = False
            else:
                st.error(f"Error saving changes: {save_response.status_code} - {save_response.text}")
        time.sleep(3)
        st.rerun()

def generate_and_reprocess_report(api_config):
    """
    結合生成報告和重新處理內容的功能。
    """
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'generate_and_reprocess_report'
    elif st.session_state.current_page != 'generate_and_reprocess_report':
        reset_states()
        st.session_state.current_page = 'generate_and_reprocess_report'
    st.header("Generate and Reprocess Report")

    access_token = get_access_token()
    if not access_token:
        st.warning("Please login first.")
        return

    if 'report_checked' not in st.session_state:
        st.session_state.report_checked = False

    if 'report_exists' not in st.session_state:
        st.session_state.report_exists = False

    if not st.session_state.report_checked:
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        check_report_response = requests.get(f"{API_BASE_URL}/check_result", headers=headers)
        if check_report_response.status_code == 200:
            st.session_state.report_exists = check_report_response.json()["result"]
        else:
            st.error("Failed to check for existing report. Please try again.")
        st.session_state.report_checked = True

    if st.session_state.report_exists:
        st.success("Generated report found. To check the report, go to 'Get Report' page.")

    # 生成報告部分
    generate_report(api_config)

    st.markdown("---")  # 分隔線

    # 重新處理內容部分
    reprocess_content(api_config)

def download_report(headers):
    """
    處理報告下載請求。
    """
    response = requests.get(f"{API_BASE_URL}/download_report", headers=headers)
    if response.status_code == 200:
        report_content = response.content
        st.download_button(
            label="Download the report",
            data=report_content,
            file_name="report.txt",
            mime="text/plain"
        )
    else:
        st.error(f"Error downloading report: {response.status_code} - {response.text}")

def logout(access_token):
    """
    創建註銷界面，允許用戶登出當前會話。
    處理註銷請求並清除訪問令牌。
    """
    delete_report = st.sidebar.checkbox("Delete report when logging out")
    if st.sidebar.button("Logout"):
        clear_access_token()
        clear_api_config()
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        if delete_report:
            requests.delete(f"{API_BASE_URL}/delete_report", headers=headers)
        else:
            requests.get(f"{API_BASE_URL}/logout", headers=headers)
        # 清除所有相關的 session state 變量
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("You have been logged out successfully. API configuration has been cleared.")
        st.rerun()

def main():
    st.title("Report Generator")

    api_config = setup_api()

    access_token = get_access_token()
    if not access_token:
        menu = ["Login", "Register"]
        choice = st.sidebar.selectbox("Menu", menu)
    else:
        menu = ["Generate and Reprocess Report", "Get Report"]
        choice = st.sidebar.selectbox("Menu", menu)
        logout(access_token)

    if choice == "Login":
        login_user()
    elif choice == "Register":
        register_user()
    elif choice == "Generate and Reprocess Report":
        generate_and_reprocess_report(api_config)
    elif choice == "Get Report":
        get_report()

if __name__ == "__main__":
    main()