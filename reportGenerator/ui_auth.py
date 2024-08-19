import streamlit as st
import requests
import time
import json
import os

API_BASE_URL = "http://127.0.0.1:8000"

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

# 設置 API
def setup_api():
    """
    在側邊欄中創建 API 設置界面，允許用戶選擇 API 類型（OpenAI 或 Azure）
    並輸入相應的 API 密鑰和（如果適用）基礎 URL。

    返回:
    dict: 包含用戶輸入的 API 配置信息
    """
    api_type = st.sidebar.selectbox("Select the API to use", ["OpenAI", "Azure"])

    if api_type == "OpenAI":
        openai_key = st.sidebar.text_input("Enter your OpenAI key", type="password")
        return {"openai_key": openai_key}
    else:
        azure_key = st.sidebar.text_input("Enter your Azure key", type="password")
        azure_base = st.sidebar.text_input("Enter your Azure base URL")
        return {"azure_key": azure_key, "azure_base": azure_base}

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

# 重置狀態
def reset_states():
    """
    重置所有相關的 session_state 變量到其初始狀態。
    這用於清理和重置應用程序的狀態。
    """
    st.session_state.current_page = 'generate_and_reprocess_report'
    st.session_state.generate_report_clicked = False
    st.session_state.reprocess_clicked = False
    st.session_state.reprocess_command = ""
    st.session_state.reprocess_result = None
    st.session_state.theme = ""
    st.session_state.num_titles = 1
    st.session_state.titles_dict = {}
    st.session_state.links = ""

# 生成報告
def generate_report(api_config):
    """
    創建報告生成界面，允許用戶輸入報告主題、標題和鏈接。
    處理報告生成請求並顯示結果。

    參數:
    api_config (dict): API 配置信息
    """

    if 'generate_report_clicked' not in st.session_state:
        st.session_state.generate_report_clicked = False
        st.session_state.reprocess_report_clicked = False

    st.header("Generate Report")

    theme = st.text_input("Enter the theme of the report")

    titles_dict = {}

    if 'num_titles' not in st.session_state:
        st.session_state.num_titles = 1

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Add Title"):
            st.session_state.num_titles += 1
    with col2:
        if st.button("Reset Titles"):
            st.session_state.num_titles = 1

    for i in range(st.session_state.num_titles):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input(f"Title {i+1}", key=f"title_{i}")
        with col2:
            subtitles = st.text_area(f"Subtitles for Title {i+1} (one per line)", key=f"subtitles_{i}")
        if title and subtitles:
            titles_dict[title] = subtitles.split('\n')

    links = st.text_area("Enter links (one per line)")
    links_list = links.split('\n') if links else []

    col1, col2 = st.columns(2)
    with col1:
        generate_report_clicked = st.button("Generate Report", key="generate_report", disabled=st.session_state.generate_report_clicked, use_container_width=True)
    with col2:
        reset_all = st.button("Reset", key="reset_all", use_container_width=True, disabled=not st.session_state.generate_report_clicked)
    if generate_report_clicked:
        st.session_state.generate_report_clicked = True
        st.rerun()
    if reset_all:
        reset_states()
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
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{API_BASE_URL}/get_report", headers=headers)
        if response.status_code == 200:
            result = response.json()
            st.json(result["result"])
        else:
            st.error(f"Error: {response.status_code} - {response.text}")

def reprocess_content():
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

    # 初始化 session state 變量
    if 'reprocess_command' not in st.session_state:
        st.session_state.reprocess_command = ""
    if 'reprocess_result' not in st.session_state:
        st.session_state.reprocess_result = None
    if 'reprocess_clicked' not in st.session_state:
        st.session_state.reprocess_clicked = False

    command = st.text_input("Enter the command for reprocess", value=st.session_state.reprocess_command)

    col1, col2 = st.columns(2)
    with col1:
        reprocess_button = st.button("Reprocess Report", disabled=st.session_state.reprocess_clicked, use_container_width=True)
    with col2:
        reset_button = st.button("Reset", use_container_width=True, disabled=not st.session_state.reprocess_clicked)

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
                "openai_config": {}  # 如果需要，添加 OpenAI 配置
            }

            headers = {"Authorization": f"Bearer {access_token}"}
            with st.spinner("Reprocessing report..."):
                response = requests.post(f"{API_BASE_URL}/reprocess_content", json=data, headers=headers)
                if response.status_code == 200:
                    st.session_state.reprocess_result = response.json()['result']
                    st.success("Content reprocessed successfully.")
                else:
                    st.error(f"Error: {response.status_code} - {response.text}")
                    st.session_state.reprocess_result = None
        st.session_state.reprocess_clicked = False

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
            headers = {"Authorization": f"Bearer {access_token}"}
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
        st.session_state.num_titles = 1
        st.session_state.generate_report_clicked = False
        st.session_state.reprocess_clicked = False
        st.session_state.current_page = 'generate_and_reprocess_report'
    st.header("Generate and Reprocess Report")

    # 生成報告部分
    generate_report(api_config)

    st.markdown("---")  # 分隔線

    # 重新處理內容部分
    reprocess_content()

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
            st.success("You have been logged out successfully.")
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