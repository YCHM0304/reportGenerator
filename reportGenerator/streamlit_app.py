import streamlit as st
import requests
import uuid
import json

# API Endpoint (replace with your actual API endpoint)
API_URL = "http://localhost:8000"

# 添加自定義CSS以創建固定大小的聊天框
st.markdown("""
<style>
.chat-container {
    border: 1px solid #ddd;
    border-radius: 5px;
    padding: 10px;
    height: 400px;
    overflow-y: auto;
    background-color: #f9f9f9;
    margin-bottom: 10px;
}
.user-message {
    background-color: #e1f5fe;
    padding: 8px 12px;
    border-radius: 15px;
    margin: 5px 0;
    max-width: 80%;
    margin-left: auto;
    text-align: right;
}
.agent-message {
    background-color: #f0f0f0;
    padding: 8px 12px;
    border-radius: 15px;
    margin: 5px 0;
    max-width: 80%;
}
</style>
""", unsafe_allow_html=True)

# 初始化會話狀態
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'preview' not in st.session_state:
    st.session_state.preview = "這裡將顯示報告預覽..."
if 'sources' not in st.session_state:
    st.session_state.sources = []
# 添加更新標誌
if 'sources_updated' not in st.session_state:
    st.session_state.sources_updated = False

# 處理提交訊息
def process_message():
    if st.session_state.user_input:
        user_message = st.session_state.user_input

        # 加入對話歷史 (client-side for immediate display)
        st.session_state.messages.append({"role": "user", "content": user_message})

        # 發送訊息到API
        try:
            response = requests.post(
                f"{API_URL}/chat",
                json={"message": user_message, "session_id": st.session_state.session_id},
                headers={"session_id": st.session_state.session_id}
            )
            data = response.json()

            # Add agent response to messages
            st.session_state.messages.append({"role": "agent", "content": data["response"]})

            # Get updated preview
            preview_response = requests.get(
                f"{API_URL}/preview",
                headers={"session_id": st.session_state.session_id}
            )
            preview_data = preview_response.json()
            st.session_state.preview = preview_data["preview"]

        except Exception as e:
            st.error(f"Error communicating with API: {str(e)}")

        # 清空輸入框
        st.session_state.user_input = ""

# 處理資料來源
def add_source():
    file = st.session_state.file_input if 'file_input' in st.session_state else None
    url = st.session_state.url_input if 'url_input' in st.session_state else ""

    try:
        if file:
            files = {"file": (file.name, file, file.type)}
            response = requests.post(
                f"{API_URL}/sources",
                files=files,
                data={"source_type": "file", "content": file.name},
                headers={"session_id": st.session_state.session_id}
            )
            if response.status_code == 200:
                st.session_state.sources = fetch_sources()
                # 設置更新標誌
                st.session_state.sources_updated = True

        elif url:
            response = requests.post(
                f"{API_URL}/sources",
                data={"source_type": "url", "content": url},
                headers={"session_id": st.session_state.session_id}
            )
            if response.status_code == 200:
                st.session_state.sources = fetch_sources()
                st.session_state.url_input = ""
                # 設置更新標誌
                st.session_state.sources_updated = True

    except Exception as e:
        st.error(f"Error adding source: {str(e)}")

# 獲取資料來源
def fetch_sources():
    try:
        response = requests.get(
            f"{API_URL}/sources",
            headers={"session_id": st.session_state.session_id}
        )
        if response.status_code == 200:
            data = response.json()
            sources = data.get("sources", [])
            # 確保返回的數據格式正確
            return [
                {
                    "id": source.get("id"),
                    "type": source.get("type"),
                    "content": source.get("content"),
                    "selected": source.get("selected", True)
                }
                for source in sources
            ]
        return []
    except Exception as e:
        st.error(f"Error fetching sources: {str(e)}")
        return []

# 切換資料來源選擇狀態
def toggle_source(source_id, selected):
    try:
        response = requests.put(
            f"{API_URL}/sources/{source_id}",
            params={"selected": selected},
            headers={"session_id": st.session_state.session_id}
        )
        if response.status_code == 200:
            # Refresh sources and preview
            st.session_state.sources = fetch_sources()

            preview_response = requests.get(
                f"{API_URL}/preview",
                headers={"session_id": st.session_state.session_id}
            )
            preview_data = preview_response.json()
            st.session_state.preview = preview_data["preview"]
    except Exception as e:
        st.error(f"Error toggling source: {str(e)}")

# 移除資料來源
def remove_source(source_id):
    try:
        response = requests.delete(
            f"{API_URL}/sources/{source_id}",
            headers={"session_id": st.session_state.session_id}
        )
        if response.status_code == 200:
            # Refresh sources and preview
            st.session_state.sources = fetch_sources()

            preview_response = requests.get(
                f"{API_URL}/preview",
                headers={"session_id": st.session_state.session_id}
            )
            preview_data = preview_response.json()
            st.session_state.preview = preview_data["preview"]

        st.rerun()
    except Exception as e:
        st.error(f"Error removing source: {str(e)}")

# 應用標題
st.title("報告生成器")

# 側邊欄: 資料來源管理
with st.sidebar:
    st.title("資料來源管理")

    st.subheader("添加參考資料")
    st.file_uploader("上傳檔案", key="file_input")
    st.text_input("輸入URL", placeholder="https://...", key="url_input")
    st.button("添加資料來源", on_click=add_source)

    st.subheader("已添加的資料來源")

    # 檢查更新標誌或需要初始載入
    if st.session_state.sources_updated or not st.session_state.sources:
        st.session_state.sources = fetch_sources()
        # 重置更新標誌
        st.session_state.sources_updated = False

    if not st.session_state.sources:
        st.info("尚未添加任何資料來源")
    else:
        for source in st.session_state.sources:
            cols = st.columns([1, 6, 1])
            with cols[0]:
                st.checkbox(
                    "選擇資料來源",
                    value=source["selected"],
                    key=f"source_{source['id']}",
                    on_change=toggle_source,
                    args=(source["id"], not source["selected"]),
                    label_visibility="collapsed"
                )
            with cols[1]:
                st.text(f"{source['type']}: {source['content']}")
            with cols[2]:
                if st.button("❌", key=f"delete_{source['id']}", help="移除此資料來源"):
                    remove_source(source["id"])

# 主內容區: 對話與報告
# 創建左右兩欄佈局
col1, col2 = st.columns(2)

with col1:
    st.subheader("與Agent討論報告內容")

    # 創建固定大小的聊天容器
    chat_container = st.container()

    # 用戶輸入框
    st.text_input("輸入訊息...", key="user_input", on_change=process_message)

    # 在聊天容器中顯示對話記錄
    with chat_container:
        # 使用HTML創建固定大小的聊天框
        chat_html = '<div class="chat-container">'

        for message in st.session_state.messages:
            if message["role"] == "user":
                chat_html += f'<div class="user-message">{message["content"]}</div>'
            else:
                chat_html += f'<div class="agent-message">{message["content"]}</div>'

        chat_html += '</div>'
        st.markdown(chat_html, unsafe_allow_html=True)

with col2:
    st.subheader("報告預覽")
    st.text_area("報告內容", value=st.session_state.preview, height=400, key="preview_area",
                 disabled=True, label_visibility="collapsed")
