import streamlit as st
import requests
import time
import json
import os
import io
from PyPDF2 import PdfReader
import base64

st.set_page_config(
        page_title="Traditional Chinese Report Generator",
        page_icon="📝" ,
)

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

    # 使用 on_change 回調來更新 session_state
    def update_api_type():
        st.session_state.api_config['api_type'] = st.session_state.api_type

    api_type = st.sidebar.selectbox(
        "Select the API to use",
        ["OpenAI", "Azure"],
        key="api_type",
        on_change=update_api_type,
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

    # 將成功訊息的位置移到外層
    message_container = st.empty()

    signup_container = st.container()
    with signup_container:
        col1, _, col3 = st.columns([1, 3, 2])
        with col1:
            if st.button("Sign Up", type="primary", use_container_width=True):
                if not username or not password or not confirm_password:
                    message_container.error("Please fill in all fields.")
                    return
                if password == confirm_password:
                    response = requests.post(f"{API_BASE_URL}/register", json={"username": username, "password": password})
                    if response.status_code == 200:
                        token = response.json()["access_token"]
                        set_access_token(token)
                        message_container.success("Registration successful. You are now logged in.")
                        time.sleep(2)
                        st.rerun()
                    else:
                        message_container.error(f"Registration failed: {response.text}")
                else:
                    message_container.error("Passwords do not match.")
        with col3:
            if st.button("I already have an account", use_container_width=True):
                if "redirect_to_signup" in st.session_state:
                    del st.session_state.redirect_to_signup
                st.rerun()

def login_user():
    """
    創建用戶登錄界面，允許現有用戶登錄。
    處理登錄請求並在成功時設置訪問令牌。
    """
    st.header("User Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    # 將成功訊息的位置移到外層
    message_container = st.empty()

    signin_container = st.container()
    with signin_container:
        col1, _, col3 = st.columns([1, 3, 1])
        with col1:
            if st.button("Login", type="primary", use_container_width=True):
                if not username or not password:
                    message_container.error("Please fill in all fields.")
                    time.sleep(2)
                    st.rerun()
                response = requests.post(f"{API_BASE_URL}/token", data={"username": username, "password": password})
                if response.status_code == 200:
                    token = response.json()["access_token"]
                    set_access_token(token)
                    message_container.success("Login successful.")
                    time.sleep(2)
                    st.rerun()
                else:
                    if response.text == '{"detail":"Incorrect username or password"}':
                        message_container.error("Incorrect username or password.")
                    else:
                        message_container.error(f"Login failed: {response.text}")
        with col3:
            if st.button("Sign Up", use_container_width=True):
                st.session_state.redirect_to_signup = True
                st.rerun()


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
    st.session_state.current_page = 'generate_and_report_status'
    st.session_state.generate_report_clicked = False
    st.session_state.reprocess_report_clicked = False
    st.session_state.recommended_main_sections = None
    st.session_state.reprocess_clicked = False
    st.session_state.reprocess_command = ""
    st.session_state.reprocess_result = None
    st.session_state.detail = None
    # st.session_state.num_main_sections = 1
    st.session_state.generate_recommend_main_sections_clicked = False

def generate_report(api_config):
    st.header("Generate Report")

    # Initialize session state variables if they don't exist
    if 'report_topic' not in st.session_state:
        st.session_state.report_topic = ""
    if 'links_input' not in st.session_state:
        st.session_state.links_input = ""
    if 'final_summary' not in st.session_state:
        st.session_state.final_summary = True
    if 'main_sections_data' not in st.session_state:
        st.session_state.main_sections_data = {}

    # Report topic input with session state
    report_topic = st.text_input(
        "Enter the report topic",
        value=st.session_state.report_topic,
        key="report_topic_input"
    )
    # Update session state when input changes
    st.session_state.report_topic = report_topic

    if 'recommended_main_sections' not in st.session_state:
        st.session_state.recommended_main_sections = None

    if 'num_main_sections' not in st.session_state:
        st.session_state.num_main_sections = 1

    # Generate recommended sections buttons
    col1, col2 = st.columns(2)
    with col1:
        generate_recommend_main_sections_clicked = st.button(
            "Generate Recommended Main Sections",
            disabled=st.session_state.generate_recommend_main_sections_clicked or st.session_state.generate_report_clicked or st.session_state.reprocess_clicked,
            help="Generate recommended main sections based on the report topic."
        )

    with col2:
        if st.button("Reset Main Sections", disabled=st.session_state.generate_recommend_main_sections_clicked):
            st.session_state.recommended_main_sections = None
            st.session_state.num_main_sections = 1
            # Clear the stored main sections data
            st.session_state.main_sections_data = {}

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

    # Add/Remove section buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Add Main Section"):
            st.session_state.num_main_sections += 1
    with col2:
        if st.button("Remove Main Section") and st.session_state.num_main_sections > 1:
            st.session_state.num_main_sections -= 1
            # Remove the last section's data from session state
            last_section_key = f"main_section_{st.session_state.num_main_sections}"
            last_subsections_key = f"subsections_{st.session_state.num_main_sections}"
            if last_section_key in st.session_state.main_sections_data:
                del st.session_state.main_sections_data[last_section_key]
            if last_subsections_key in st.session_state.main_sections_data:
                del st.session_state.main_sections_data[last_subsections_key]

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

    main_sections_dict = {}

    # Create main sections with persistent values
    for i in range(st.session_state.num_main_sections):
        col1, col2 = st.columns(2)
        with col1:
            main_section_key = f"main_section_{i}"
            default_main_section = ""

            # Get value from recommended sections if available
            if st.session_state.recommended_main_sections and i < len(st.session_state.recommended_main_sections["主要部分"]):
                default_main_section = st.session_state.recommended_main_sections["主要部分"][i]
            # Otherwise get from session state if available
            elif main_section_key in st.session_state.main_sections_data:
                default_main_section = st.session_state.main_sections_data[main_section_key]

            main_section = st.text_input(
                f"Main Section {i+1}",
                value=default_main_section,
                key=f"main_section_input_{i}"
            )
            # Store in session state
            st.session_state.main_sections_data[main_section_key] = main_section

        with col2:
            subsections_key = f"subsections_{i}"
            default_subsections = ""

            # Get value from recommended sections if available
            if st.session_state.recommended_main_sections and i < len(st.session_state.recommended_main_sections["次要部分"]):
                default_subsections = "\n".join(st.session_state.recommended_main_sections["次要部分"][i])
            # Otherwise get from session state if available
            elif subsections_key in st.session_state.main_sections_data:
                default_subsections = st.session_state.main_sections_data[subsections_key]

            subsections = st.text_area(
                f"Subsections for Main Section {i+1} (one per line)",
                value=default_subsections,
                key=f"subsections_input_{i}"
            )
            # Store in session state
            st.session_state.main_sections_data[subsections_key] = subsections

        if main_section and subsections:
            main_sections_dict[main_section] = subsections.split('\n')

    st.info("**Note**: *Some of the links may not be accessible due to the policy of the website.*")
    default_links = st.session_state.links_input
    # Links input with session state
    links = st.text_area(
        "Enter links (one per line)",
        value=default_links,
        key="links_input_key"
    )
    st.session_state.links_input = links

    links_list = links.split('\n') if links else []
    links_list = [link for link in links_list if link]

    # Final summary toggle with session state
    final_summary = st.toggle(
        "Generate final summary",
        value=st.session_state.final_summary,
        help="Generate an extra final summary based on the generated contents.",
        key="final_summary_toggle"
    )
    # Update session state when toggle changes
    st.session_state.final_summary = final_summary

    col1, col2 = st.columns(2)
    with col1:
        generate_report_clicked = st.button(
            "Generate Report",
            key="generate_report",
            disabled=st.session_state.generate_report_clicked or st.session_state.reprocess_clicked,
            use_container_width=True
        )
    with col2:
        if st.button("Reset All", key="reset_all", use_container_width=True, disabled=st.session_state.generate_report_clicked or st.session_state.reprocess_clicked):
            # Clear all stored form data
            st.session_state.report_topic = ""
            st.session_state.links_input = ""
            st.session_state.final_summary = True
            st.session_state.main_sections_data = {}
            st.session_state.num_main_sections = 1
            reset_states()
            st.session_state.recommended_main_sections = None
            st.rerun()

    if generate_report_clicked:
        if not report_topic or not main_sections_dict or not links_list:
            st.error("Please fill in all fields.")
            return
        st.session_state.generate_report_clicked = True
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

def get_report(api_config):
    """
    創建獲取報告界面，允許用戶查看和編輯報告內容。
    報告的編輯功能專注於內容的修改，保持結構的一致性。
    """
    st.session_state.current_page = 'get_report'

    access_token = get_access_token()
    if not access_token:
        st.warning("Please login first.")
        return

    # 初始化編輯狀態
    if 'editing_sections' not in st.session_state:
        st.session_state.editing_sections = None
    if 'edit_report_clicked' not in st.session_state:
        st.session_state.edit_report_clicked = False
    if 'reprocess_report_clicked' not in st.session_state:
        st.session_state.reprocess_report_clicked = False

    if not st.session_state.reprocess_report_clicked:
        st.header("View and Edit report")

    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    response = requests.get(f"{API_BASE_URL}/get_report", headers=headers)

    if response.status_code == 200:
        result = response.json()
        if not st.session_state.reprocess_report_clicked:
            # 創建按鈕列
            col1, col2 = st.columns(2)
            with col1:
                edit_button = st.button(
                    "Edit Report",
                    disabled=st.session_state.edit_report_clicked,
                    use_container_width=True
                )

            with col2:
                if st.session_state.edit_report_clicked:
                    if st.button("Cancel", use_container_width=True):
                        st.session_state.editing_sections = None
                        st.session_state.edit_report_clicked = False
                        st.rerun()
                else:
                    if st.button("Edit with AI", use_container_width=True):
                        st.session_state.reprocess_report_clicked = True
                        st.rerun()
        else:
            edit_button = False

        if st.session_state.reprocess_report_clicked:
            reprocess_content(api_config)

        # 顯示報告內容（改進的部分）
        if not st.session_state.editing_sections and not st.session_state.reprocess_report_clicked:
            report_data = result["result"]

            # 使用卡片式布局顯示報告內容
            st.subheader("Report Details")

            # 顯示報告主題和時間戳（如果存在）
            if "report_topic" in report_data:
                st.markdown(f"**Topic:** {report_data['report_topic']}")
            if "timestamp" in report_data:
                st.markdown(f"**Generated at:** {report_data['timestamp']}")

            # 為每個報告部分創建展開區域
            for section, content in report_data.items():
                if section not in ["report_topic", "timestamp"]:
                    with st.expander(f"📑 {section}", expanded=True):
                        # 使用markdown顯示內容，保持格式
                        st.markdown(content)
                        # 添加分隔線
                        st.divider()

            # 下載和返回按鈕
            download_container = st.container()
            with download_container:
                col1, col2 = st.columns([2, 1])
                with col1:
                    download_report(headers)
                with col2:
                    if st.button("Back to Report Generation", use_container_width=True):
                        if 'redirect_to_report' in st.session_state:
                            del st.session_state.redirect_to_report
                        st.rerun()

        # 編輯功能保持不變
        if edit_button:
            st.session_state.edit_report_clicked = True
            report_content = result["result"]
            st.session_state.editing_sections = {
                "主要部分": [],
                "內容": []
            }
            for section, content in report_content.items():
                if section not in ["report_topic", "timestamp"]:
                    st.session_state.editing_sections["主要部分"].append(section)
                    st.session_state.editing_sections["內容"].append(content)
            st.rerun()

        if st.session_state.edit_report_clicked and st.session_state.editing_sections:
            st.info("Edit the content below.")
            edited_content = {}

            for i in range(len(st.session_state.editing_sections["主要部分"])):
                with st.expander(f"Section {i+1}: {st.session_state.editing_sections['主要部分'][i]}", expanded=True):
                    new_section = st.text_input("Edit Section", value=f"{st.session_state.editing_sections['主要部分'][i]}")
                    new_content = st.text_area(
                        "Edit Content",
                        value=st.session_state.editing_sections["內容"][i],
                        height=300,
                        key=f"section_content_{i}",
                        help="Modify the content while keeping the section structure"
                    )
                    edited_content[new_section] = new_content

            if st.button("Save Changes", type="primary"):
                save_success = True
                for section, content in edited_content.items():
                    save_data = {
                        "main_section": section,
                        "new_content": content,
                        "edit_mode": True
                    }
                    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
                    save_response = requests.post(f"{API_BASE_URL}/save_reprocessed_content", json=save_data, headers=headers)
                    if save_response.status_code != 200:
                        save_success = False
                        st.error(f"Error saving changes for section '{section}': {save_response.status_code} - {save_response.text}")
                if save_success:
                    st.success("Changes saved successfully.")
                    st.session_state.editing_sections = None
                    st.session_state.edit_report_clicked = False
                    time.sleep(2)
                    st.rerun()

    elif response.text == '{"detail":"報告尚未生成"}':
        st.warning("Report not generated yet. Please generate a report first.")
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

    # Style selection
    style_selection = style_selection_ui()
    example_text = None
    if style_selection is not None:
        if style_selection.startswith("AI: "):
            example_text = style_selection[4:]
            style_selection = None

    more_info_from_links = st.toggle("Additional Information Source URLs", value=False, help='Add more URLs to expand the data sources for your report.')
    if more_info_from_links:
        links = st.text_area("Enter links (one per line)", key=more_info_from_links)
        links_list = links.split('\n') if links else []
        links_list = [link for link in links_list if link]

    col1, col2 = st.columns(2)
    with col1:
        reprocess_button = st.button("Reprocess Report", disabled=st.session_state.reprocess_clicked or st.session_state.generate_report_clicked, use_container_width=True, type="primary")
    with col2:
        reset_button = st.button("Reset", use_container_width=True, disabled=st.session_state.reprocess_clicked or st.session_state.generate_report_clicked)

    _, col2 = st.columns(2)
    with col2:
        if st.button("Cancel", use_container_width=True, disabled=st.session_state.reprocess_clicked):
            st.session_state.reprocess_report_clicked = False
            st.rerun()

    if reprocess_button:
        if not command:
            st.error("Command is required.")
            return
        if more_info_from_links and not links_list:
            st.error("Please enter at least one link.")
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
            "links": links_list if more_info_from_links else None,
            "style_selection": style_selection,
            "example_text": example_text
        }

        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        with st.spinner("Reprocessing report..."):
            response = requests.post(f"{API_BASE_URL}/reprocess_content", json=data, headers=headers)
            if response.status_code == 422 and "requires_user_input" in response.json().get("detail", {}):
                if response.json()["detail"]["requires_user_input"]:
                    st.session_state.user_decision_required = True
                    st.session_state.detail = response.json()["detail"]
                    st.rerun()
            elif response.status_code == 200:
                st.session_state.reprocess_result = response.json()['result']
                st.success("Content reprocessed successfully.")
            elif response.status_code == 400:
                        if response.text == '{"detail":"請先使用generate_report生成報告"}':
                            st.warning("Please generate a report first.")
                        elif response.text == '{"detail":"請提供OpenAI或Azure的API金鑰"}':
                            st.warning("Please provide OpenAI or Azure API key.")
            else:
                st.error(f"Error: {response.status_code} - {response.text}")
                st.session_state.reprocess_result = None

        time.sleep(3)
        st.session_state.reprocess_clicked = False
        st.rerun()

    if st.session_state.get('user_decision_required', False):
        detail = st.session_state.detail
        st.warning(detail["message"])
        user_decision = st.radio(
            detail["input_question"],
            options=["Yes", "No"],
            key="user_decision"
        )

        if st.button("Submit Decision"):
            user_decision_bool = user_decision == "Yes"
            data = {
                "command": st.session_state.reprocess_command,
                "openai_config": api_config,
                "links": links_list if more_info_from_links else None,
                "style_selection": style_selection,
                "user_decision": user_decision_bool
            }
            headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
            with st.spinner("Reprocessing report with user decision..."):
                response = requests.post(f"{API_BASE_URL}/reprocess_content", json=data, headers=headers)

            if response.status_code == 200:
                st.session_state.reprocess_result = response.json()['result']
                st.success("Content reprocessed successfully.")
            else:
                st.error(f"Error: {response.status_code} - {response.text}")

            st.session_state.user_decision_required = False
            st.rerun()

    if st.session_state.reprocess_result:
        result = st.session_state.reprocess_result
        st.write(f"Main Section: {result['main_section']}")
        st.subheader("Original content:")
        st.write(result['original_content'])
        st.subheader("Modified content:")
        st.write(result['modified_content'])

        if st.button("Save Changes", type="primary"):
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

def generate_and_report_status(api_config):
    """
    結合生成報告和重新處理內容的功能。
    """
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'generate_and_report_status'
    elif st.session_state.current_page != 'generate_and_report_status':
        reset_states()
        st.session_state.current_page = 'generate_and_report_status'

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
        st.success("Generated report found. Click the button to check the report.")
        _, col2 = st.columns([2, 1])
        with col2:
             if st.button("View and Edit Report", use_container_width=True):
                st.session_state.redirect_to_report = True
                st.rerun()

    # 生成報告部分
    generate_report(api_config)

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
            mime="text/plain",
            type="primary"
        )
    else:
        st.error(f"Error downloading report: {response.status_code} - {response.text}")

def get_predefined_styles():
    """
    返回預定義的風格選項列表。
    """
    return [
        {"name": "專業", "description": "使用正式、客觀的語言，適合商業報告"},
        {"name": "通俗易懂", "description": "使用簡單、直白的語言，適合大眾閱讀"},
        {"name": "學術", "description": "使用專業術語和引用，適合學術論文"},
        {"name": "幽默", "description": "加入輕鬆、有趣的表達，適合非正式場合"},
        {"name": "激勵", "description": "使用鼓舞人心的語言，適合演講稿"},
    ]

def extract_text_from_file(uploaded_file):
    if uploaded_file.type == "text/plain":
        return uploaded_file.getvalue().decode("utf-8")
    elif uploaded_file.type == "application/pdf":
        pdf_reader = PdfReader(io.BytesIO(uploaded_file.getvalue()))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    else:
        st.error("Unsupported file type")
        return None

def style_selection_ui():
    col1, col2 = st.columns(2)

    with col1:
        style_option = st.radio(
            "Select a style option",
            ["Original Style", "Predefined Style", "Custom Style", "AI-generated Style"],
            captions=[
                "Use the original style of the content.",
                "Select a predefined style from the list.",
                "Describe your custom style.",
                "Let AI generate a style based on the content."
            ],
            help="Select the style option for the reprocessing command."
        )

    selected_style = None

    with col2:
        if style_option == "Predefined Style":
            styles = get_predefined_styles()
            selected_style = st.selectbox(
                "Select a predefined style",
                options=[style["name"] for style in styles],
                format_func=lambda x: f"{x} - {next(style['description'] for style in styles if style['name'] == x)}"
            )

        elif style_option == "Custom Style":
            custom_style = st.text_area("Describe your custom style", help="e.g. 正式且專業")
            if custom_style:
                selected_style = custom_style
        elif style_option == "AI-generated Style":
            st.info("AI-generated style will be selected automatically based on the content.")
            uploaded_file = st.file_uploader("Upload an example file for AI to generate the report with the similar style", type=["txt", "pdf"])
            if uploaded_file:
                example_text = extract_text_from_file(uploaded_file)
                if example_text:
                    selected_style = "AI: " + example_text
                    st.success("Uploaded file processed successfully.")
                else:
                    st.error("Failed to extract text from the uploaded file.")

    return selected_style

def logout(access_token):
    """
    創建註銷界面，允許用戶登出當前會話。
    處理註銷請求並清除訪問令牌。
    """
    delete_report = st.sidebar.toggle("Delete report when logging out")
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

    access_token = get_access_token()
    if not access_token:
        choice = "Sign Up" if st.session_state.get('redirect_to_signup', False) else "Login"
    else:
        # 檢查是否需要重定向到報告頁面
        choice = "Get Report" if st.session_state.get('redirect_to_report', False) else "Generate and Reprocess Report"


    if choice == "Login":
        login_user()
    elif choice == "Sign Up":
        register_user()
    elif choice == "Generate and Reprocess Report":
        api_config = setup_api()
        logout(access_token)
        generate_and_report_status(api_config)
    elif choice == "Get Report":
        api_config = setup_api()
        logout(access_token)
        get_report(api_config)


if __name__ == "__main__":
    main()