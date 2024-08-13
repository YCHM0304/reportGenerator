import streamlit as st
import requests
import json
import os

# API 基礎 URL
API_BASE_URL = "http://127.0.0.1:8000"

# 獲取當前會話 ID
def get_session_id():
    """Get the current session ID from Streamlit's session state."""
    return st.session_state.get('session_id', None)

# 設置會話 ID
def set_session_id(session_id):
    """Set the session ID in Streamlit's session state."""
    st.session_state['session_id'] = session_id

# 清除會話 ID
def clear_session_id():
    """Clear the session ID from Streamlit's session state."""
    if 'session_id' in st.session_state:
        del st.session_state['session_id']

# 設置 API
def setup_api():
    api_type = st.sidebar.selectbox("Select the API to use", ["OpenAI", "Azure"])

    if api_type == "OpenAI":
        openai_key = st.sidebar.text_input("Enter your OpenAI key", type="password")
        return {"openai_key": openai_key}
    else:
        azure_key = st.sidebar.text_input("Enter your Azure key", type="password")
        azure_base = st.sidebar.text_input("Enter your Azure base URL")
        return {"azure_key": azure_key, "azure_base": azure_base}

# 處理會話 ID 輸入
def handle_session_id_input():
    st.sidebar.header("Session Management")

    current_session_id = get_session_id()
    if current_session_id:
        st.sidebar.info(f"Current Session ID: {current_session_id}")

    new_session_id = st.sidebar.text_input("Enter Session ID (optional)", value="")

    if st.sidebar.button("Use This Session ID"):
        if new_session_id:
            # 驗證會話 ID
            if len(new_session_id.strip()) > 0:
                set_session_id(new_session_id)
                st.sidebar.success(f"Session ID updated to: {new_session_id}")
                st.rerun()  # 重新運行
            else:
                st.sidebar.error("Invalid Session ID")

    if st.sidebar.button("Clear Session ID"):
        clear_session_id()
        st.sidebar.success("Session ID cleared")
        st.rerun()  # Rerun the app to reflect changes

def reset_states():
    st.session_state.current_page = 'generate_report'
    st.session_state.generate_report_clicked = False
    st.session_state.reprocess_report_clicked = False
    st.session_state.theme = ""
    st.session_state.num_titles = 1
    st.session_state.titles_dict = {}
    st.session_state.links = ""

# 生成報告
def generate_report(api_config):
    # Initialize or update current page state
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'generate_report'
    elif st.session_state.current_page != 'generate_report':
        # Reset num_titles when coming from a different page
        st.session_state.num_titles = 1
        st.session_state.generate_report_clicked = False
        st.session_state.current_page = 'generate_report'

    # Initialize button states
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
        if st.button("Add Title", key="add_title"):
            st.session_state.num_titles += 1
    with col2:
        if st.button("Reset Titles", key="reset_titles"):
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

    # Place Generate Report and Reset All buttons side by side
    col1, col2 = st.columns(2)
    with col1:
        generate_report_clicked = st.button("Generate Report", key="generate_report", disabled=st.session_state.generate_report_clicked, use_container_width=True)
    with col2:
        reset_all = st.button("Reset All", key="reset_all", use_container_width=True, disabled=not st.session_state.generate_report_clicked)
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

            session_id = get_session_id()
            headers = {"session_id": session_id} if session_id else {}

            with st.spinner("Generating report..."):
                response = requests.post(f"{API_BASE_URL}/generate_report", json=data, headers=headers, verify=False)
                if response.status_code == 200:
                    result = response.json()
                    set_session_id(result["session_id"])
                    st.success(f"Report generated successfully. Session ID: {result['session_id']}. Total time: {result['total_time']} seconds.")
                else:
                    st.error(f"Error: {response.status_code} - {response.text}")
        st.session_state.generate_report_clicked = False


# def check_report():
#     st.header("Check Report Status")

#     session_id = get_session_id()
#     if not session_id:
#         st.warning("No active session. Generate a report first.")
#         return

#     if st.button("Check Status"):
#         response = requests.get(f"{API_BASE_URL}/check_result", headers={"session_id": session_id})
#         if response.status_code == 200:
#             result = response.json()
#             st.info(f"Result available: {result['result']}")
#         else:
#             st.error(f"Error: {response.status_code} - {response.text}")

# 獲取報告
def get_report():
    # Initialize or update current page state
    st.session_state.current_page = 'get_report'
    st.header("Get Report")

    session_id = get_session_id()
    if not session_id:
        st.warning("No active session. Generate a report first.")
        return

    if st.button("Get Report", disabled=st.session_state.generate_report_clicked or st.session_state.reprocess_report_clicked):
        response = requests.get(f"{API_BASE_URL}/get_report", headers={"session_id": session_id})
        if response.status_code == 200:
            result = response.json()
            st.json(result["result"])
        else:
            st.error(f"Error: {response.status_code} - {response.text}")

# 重新處理內容
def reprocess_content():
    st.header("Reprocess Content")
    st.session_state.reprocess_report_clicked = False
    session_id = get_session_id()

    # Initialize button states
    st.session_state.current_page = 'reprocess_content'

    if not session_id:
        st.warning("No active session. Generate a report first.")
        return

    command = st.text_input("Enter the command for reprocess")

        # Place Generate Report and Reset All buttons side by side
    col1, col2 = st.columns(2)
    with col1:
        reprocess_report_clicked = st.button("Reprocess Report", key="reprocess_report", disabled=st.session_state.reprocess_report_clicked, use_container_width=True)
    with col2:
        reset_all = st.button("Reset All", key="reset_all", use_container_width=True, disabled=not st.session_state.reprocess_report_clicked)
    if reprocess_report_clicked:
        st.session_state.reprocess_report_clicked = True
        st.rerun()
    if reset_all:
        reset_states()
        st.rerun()

    if st.session_state.reprocess_report_clicked:
        if not command:
            st.error("Command is required.")
            return

        data = {
            "command": command,
            "openai_config": {}  # 如果需要，添加 OpenAI 配置
        }

        with st.spinner("Reprocessing report..."):
            response = requests.post(f"{API_BASE_URL}/reprocess_content", json=data, headers={"session_id": session_id})
            if response.status_code == 200:
                result = response.json()
                st.success("Content reprocessed successfully:")
                st.write(f"Part: {result['result']['part']}")
                st.subheader("Original content:")
                st.write(result['result']['original_content'])
                st.subheader("Modified content:")
                st.write(result['result']['modified_content'])
            else:
                st.error(f"Error: {response.status_code} - {response.text}")
        st.session_state.reprocess_report_clicked = False
# 刪除會話
def delete_session():
    st.session_state.current_page = 'delete_session'
    st.header("Delete Session")

    if st.button("Delete Session", disabled=st.session_state.generate_report_clicked or st.session_state.reprocess_report_clicked):
        session_id = get_session_id()
        if session_id:
            response = requests.delete(f"{API_BASE_URL}/delete_session", headers={"session_id": session_id})
            if response.status_code == 200:
                clear_session_id()
                st.success("Session deleted successfully.")
            else:
                st.error(f"Error deleting session: {response.status_code} - {response.text}")
        else:
            st.info("No active session to delete.")

# 主函數
def main():
    st.title("Report Generator")

    api_config = setup_api()
    handle_session_id_input()

    menu = ["Generate Report", "Get Report", "Reprocess Content", "Delete Session"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Generate Report":
        generate_report(api_config)
    elif choice == "Get Report":
        get_report()
    elif choice == "Reprocess Content":
        reprocess_content()
    elif choice == "Delete Session":
        delete_session()

if __name__ == "__main__":
    main()