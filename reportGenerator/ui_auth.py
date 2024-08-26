import streamlit as st
import requests
import time
import json
import os
import time

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

# # 設置 API
# def setup_api():
#     """
#     在側邊欄中創建 API 設置界面，允許用戶選擇 API 類型（OpenAI 或 Azure）
#     並輸入相應的 API 密鑰和（如果適用）基礎 URL。

#     返回:
#     dict: 包含用戶輸入的 API 配置信息
#     """
#     api_type = st.sidebar.selectbox("Select the API to use", ["OpenAI", "Azure"])

#     if api_type == "OpenAI":
#         openai_key = st.sidebar.text_input("Enter your OpenAI key", type="password")
#         return {"openai_key": openai_key}
#     else:
#         azure_key = st.sidebar.text_input("Enter your Azure key", type="password")
#         azure_base = st.sidebar.text_input("Enter your Azure base URL")
#         return {"azure_key": azure_key, "azure_base": azure_base}
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
    if 'generate_recommend_titles_clicked' not in st.session_state:
        st.session_state.generate_recommend_titles_clicked = False

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

# 用戶註冊
def register_user():
    """
    創建用戶註冊界面，允許新用戶註冊賬戶。
    處理註冊請求並在成功時設置訪問令牌。
    """
    st.header("User Registration")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Register"):
        response = requests.post(f"{API_BASE_URL}/register", json={"username": username, "password": password})
        if response.status_code == 200:
            token = response.json()["access_token"]
            set_access_token(token)
            st.success("Registration successful. You are now logged in.")
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"Registration failed: {response.text}")

# 用戶登入
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

def generate_recommend_titles(api_config, theme):
    data = {
        "theme": theme,
        "titles": {},
        "links": [],
        "openai_config": api_config
    }

    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}

    with st.spinner("Generating recommended titles..."):
        response = requests.post(f"{API_BASE_URL}/generate_recommend_titles", json=data, headers=headers)
        if response.status_code == 200:
            result = response.json()
            st.success("Recommended titles generated successfully.")
            try:
                # 嘗試解析返回的 JSON 字符串
                titles = json.loads(result["result"])
                if isinstance(titles, dict) and "段落標題" in titles and "段落次標題" in titles:
                    return titles
                else:
                    st.error("Received data is not in the expected format.")
                    return None
            except json.JSONDecodeError:
                st.error("Failed to parse the received data.")
                return None
        else:
            st.error(f"Error: {response.status_code} - {response.text}")
            return None

# 重置狀態
def reset_states():
    """
    重置所有相關的 session_state 變量到其初始狀態。
    這用於清理和重置應用程序的狀態。
    """
    st.session_state.current_page = 'generate_and_reprocess_report'
    st.session_state.generate_report_clicked = False
    st.session_state.reprocess_report_clicked = False
    st.session_state.recommended_titles = None
    st.session_state.reprocess_clicked = False
    st.session_state.reprocess_command = ""
    st.session_state.reprocess_result = None
    st.session_state.theme = ""
    st.session_state.num_titles = 1
    st.session_state.titles_dict = {}
    st.session_state.links = ""

# 生成報告
def generate_report(api_config):
    st.header("Generate Report")

    theme = st.text_input("Enter the theme of the report")

    if 'recommended_titles' not in st.session_state:
        st.session_state.recommended_titles = None

    if 'num_titles' not in st.session_state:
        st.session_state.num_titles = 1

    col1, col2 = st.columns(2)
    with col1:
        generate_recommend_titles_clicked = st.button("Generate Recommended Titles", disabled=st.session_state.generate_recommend_titles_clicked or st.session_state.generate_report_clicked or st.session_state.reprocess_clicked)

    with col2:
        if st.button("Reset Titles", disabled=st.session_state.generate_recommend_titles_clicked):
            st.session_state.recommended_titles = None
            st.session_state.num_titles = 1

    if generate_recommend_titles_clicked:
            st.session_state.generate_recommend_titles_clicked = True
            st.rerun()
    if st.session_state.generate_recommend_titles_clicked:
        if theme:
            st.session_state.recommended_titles = generate_recommend_titles(api_config, theme)
            if st.session_state.recommended_titles:
                    st.session_state.num_titles = len(st.session_state.recommended_titles["段落標題"])
        else:
            st.error("Please enter a theme before generating titles.")
        time.sleep(2)
        st.session_state.generate_recommend_titles_clicked = False
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Add Title"):
            st.session_state.num_titles += 1
    with col2:
        if st.button("Remove Title") and st.session_state.num_titles > 1:
            st.session_state.num_titles -= 1

    titles_dict = {}

    for i in range(st.session_state.num_titles):
        col1, col2 = st.columns(2)
        with col1:
            title_key = f"title_{i}"
            default_title = ""
            if st.session_state.recommended_titles and i < len(st.session_state.recommended_titles["段落標題"]):
                default_title = st.session_state.recommended_titles["段落標題"][i]
            title = st.text_input(f"Title {i+1}", key=title_key, value=default_title)
        with col2:
            subtitles_key = f"subtitles_{i}"
            default_subtitles = ""
            if st.session_state.recommended_titles and i < len(st.session_state.recommended_titles["段落次標題"]):
                default_subtitles = "\n".join(st.session_state.recommended_titles["段落次標題"][i])
            subtitles = st.text_area(f"Subtitles for Title {i+1} (one per line)", key=subtitles_key, value=default_subtitles)
        if title and subtitles:
            titles_dict[title] = subtitles.split('\n')

    links = st.text_area("Enter links (one per line)")
    links_list = links.split('\n') if links else []

    col1, col2 = st.columns(2)
    with col1:
        generate_report_clicked = st.button("Generate Report", key="generate_report", disabled=st.session_state.generate_report_clicked or st.session_state.reprocess_clicked, use_container_width=True)
    with col2:
        reset = st.button("Reset All", key="reset_all", use_container_width=True, disabled=st.session_state.generate_report_clicked or st.session_state.reprocess_clicked)

    if generate_report_clicked:
        st.session_state.generate_report_clicked = True
        st.rerun()
    if reset:
        reset_states()
        st.session_state.recommended_titles = None
        st.rerun()

    if st.session_state.generate_report_clicked:
        if not theme or not titles_dict or not links_list:
            st.error("Please fill in all fields.")
            st.rerun()
        else:
            data = {
                "theme": theme,
                "titles": titles_dict,
                "links": links_list,
                "openai_config": api_config
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
        time.sleep(2)
        st.session_state.generate_report_clicked = False
        st.rerun()

# 取得報告
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

    if st.button("Get Report", disabled=st.session_state.generate_report_clicked or st.session_state.reprocess_report_clicked):
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        response = requests.get(f"{API_BASE_URL}/get_report", headers=headers)
        if response.status_code == 200:
            result = response.json()
            st.json(result["result"])
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

    command = st.text_input("Enter the command for reprocess", value=st.session_state.reprocess_command)

    col1, col2 = st.columns(2)
    with col1:
        reprocess_button = st.button("Reprocess Report", disabled=st.session_state.reprocess_clicked or st.session_state.generate_report_clicked, use_container_width=True)
    with col2:
        reset_button = st.button("Reset", use_container_width=True, disabled=st.session_state.reprocess_clicked or st.session_state.generate_report_clicked)

    if reprocess_button:
        st.session_state.reprocess_clicked = True
        st.rerun()

    if reset_button:
        reset_states()
        st.rerun()

    if st.session_state.reprocess_clicked:
        if not command:
            st.error("Command is required.")
        else:
            st.session_state.reprocess_clicked = True
            st.session_state.reprocess_command = command
            data = {
                "command": command,
                "openai_config": api_config
            }

            headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
            with st.spinner("Reprocessing report..."):
                response = requests.post(f"{API_BASE_URL}/reprocess_content", json=data, headers=headers)
                if response.status_code == 200:
                    st.session_state.reprocess_result = response.json()['result']
                    st.success("Content reprocessed successfully.")
                else:
                    st.error(f"Error: {response.status_code} - {response.text}")
                    st.session_state.reprocess_result = None
        time.sleep(2)
        st.session_state.reprocess_clicked = False
        st.rerun()

    if st.session_state.reprocess_result:
        result = st.session_state.reprocess_result
        st.write(f"Part: {result['part']}")
        st.subheader("Original content:")
        st.write(result['original_content'])
        st.subheader("Modified content:")
        st.write(result['modified_content'])

        if st.button("Save Changes"):
            save_data = {
                "part": result['part'],
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
        time.sleep(2)
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
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    check_report_response = requests.get(f"{API_BASE_URL}/check_result", headers=headers)
    if check_report_response.status_code == 200:
        report_exists = check_report_response.json()["result"]
        if report_exists:
            st.success("Generated report found. To check the report, go to 'Get Report' page.")
    else:
        st.error("Failed to check for existing report. Please try again.")

    # 生成報告部分
    generate_report(api_config)

    st.markdown("---")  # 分隔線

    # 重新處理內容部分
    reprocess_content(api_config)

# 登出
# def logout():
#     """
#     創建註銷界面，允許用戶登出當前會話。
#     處理註銷請求並清除訪問令牌。
#     """
#     st.session_state.current_page = 'logout'
#     st.header("Logout")

#     if st.button("Logout", disabled=st.session_state.generate_report_clicked or st.session_state.reprocess_report_clicked):
#         clear_access_token()
#         st.success("You have been logged out successfully.")
#         st.rerun()

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
        if st.sidebar.button("Logout"):
            clear_access_token()
            clear_api_config()
            st.success("You have been logged out successfully. API configuration has been cleared.")
            st.rerun()

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