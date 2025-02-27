import streamlit as st
import time
import uuid

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

class Agent:
    def __init__(self):
        self.history = []
        self.sources = []
        self.selected_sources = set()

    def respond(self, message):
        # 這裡可以接入實際的agent邏輯
        response = f"Agent回應: {message}"
        return response

    def add_source(self, file=None, url=None):
        try:
            source_id = str(uuid.uuid4())
            if file is not None:
                self.sources.append({"id": source_id, "type": "file", "content": file.name, "selected": True})
            if url and url.strip():
                self.sources.append({"id": source_id, "type": "url", "content": url.strip(), "selected": True})
            return True
        except Exception as e:
            return False

    def toggle_source(self, source_id, selected):
        for source in self.sources:
            if source["id"] == source_id:
                source["selected"] = selected
                return True
        return False

    def remove_source(self, source_id):
        self.sources = [s for s in self.sources if s["id"] != source_id]

# 初始化會話狀態
if 'agent' not in st.session_state:
    st.session_state.agent = Agent()
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'preview' not in st.session_state:
    st.session_state.preview = "這裡將顯示報告預覽..."

# 處理提交訊息
def process_message():
    if st.session_state.user_input:
        user_message = st.session_state.user_input

        # 加入對話歷史
        st.session_state.messages.append({"role": "user", "content": user_message})

        # 獲取Agent回應
        response = st.session_state.agent.respond(user_message)
        st.session_state.messages.append({"role": "agent", "content": response})

        # 更新預覽 (實際應用中可以基於對話內容生成報告)
        st.session_state.preview = f"根據討論生成的報告預覽...\n\n{user_message}"

        # 清空輸入框
        st.session_state.user_input = ""

# 處理資料來源
def add_source():
    file = st.session_state.file_input if 'file_input' in st.session_state else None
    url = st.session_state.url_input if 'url_input' in st.session_state else ""

    if file or url:
        st.session_state.agent.add_source(file, url)
        # 清空URL輸入框
        st.session_state.url_input = ""

# 切換資料來源選擇狀態
def toggle_source(source_id, selected):
    st.session_state.agent.toggle_source(source_id, selected)

# 移除資料來源
def remove_source(source_id):
    st.session_state.agent.remove_source(source_id)
    st.rerun()

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

    if not st.session_state.agent.sources:
        st.info("尚未添加任何資料來源")
    else:
        for source in st.session_state.agent.sources:
            cols = st.columns([1, 6, 1])
            with cols[0]:
                st.checkbox("", value=source["selected"], key=f"source_{source['id']}",
                            on_change=toggle_source,
                            args=(source["id"], not source["selected"]))
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

    # 添加空白行
    st.markdown("<br>", unsafe_allow_html=True)

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
    st.text_area("", value=st.session_state.preview, height=400, key="preview_area", disabled=True)