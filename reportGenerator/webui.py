import gradio as gr
import time

class Agent:
    def __init__(self):
        self.history = []
        self.sources = []

    def respond(self, message):
        # 這裡可以接入實際的agent邏輯
        response = f"Agent回應: {message}"
        return response

    def add_source(self, file=None, url=None):
        try:
            if file and hasattr(file, 'name'):
                self.sources.append({"type": "file", "content": file.name})
            if url and url.strip():
                self.sources.append({"type": "url", "content": url.strip()})
            return "\n".join([f"- {s['type']}: {s['content']}" for s in self.sources])
        except Exception as e:
            return f"處理資料來源時發生錯誤: {str(e)}"

def process_message(message, history, chatbot, agent_state):
    if not message:
        return "", history, chatbot, ""

    # 將用戶輸入的訊息添加到對話歷史中
    history.append({"role": "User", "content": message})
    chatbot.append((message, None))

    # 使用Agent回應
    response = agent_state.respond(message)
    history.append({"role": "Agent", "content": response})
    chatbot[-1] = (message, response)

    # 更新預覽
    preview = "根據討論生成的報告預覽..."

    return "", history, chatbot, preview

def handle_source(file, url, sources_status, agent_state):
    if not file and not url:
        return sources_status, None, ""

    try:
        status = agent_state.add_source(file, url)
        # 清空時返回 None 代表清空檔案上傳器
        return status, None, ""
    except Exception as e:
        return f"添加資料來源時發生錯誤: {str(e)}", None, ""

with gr.Blocks(css="#chatbot {height: 500px}") as demo:
    # 創建一個Agent實例並保持狀態
    agent_state = gr.State(Agent())

    with gr.Tabs():
        # 對話和報告預覽標籤頁
        with gr.Tab("對話與報告"):
            with gr.Row():
                # 左側對話區
                with gr.Column(scale=1):
                    gr.HTML("<h2>與Agent討論報告內容</h2>")
                    chatbot = gr.Chatbot(
                        [],
                        elem_id="chatbot",
                        height=500,
                        bubble_full_width=False,
                    )
                    msg = gr.Textbox(
                        show_label=False,
                        placeholder="輸入訊息...",
                    )

                # 右側預覽區
                with gr.Column(scale=1):
                    gr.HTML("<h2>報告預覽</h2>")
                    preview = gr.Textbox(
                        show_label=False,
                        placeholder="這裡將顯示報告預覽...",
                        lines=20,
                    )

        # 資料來源管理標籤頁
        with gr.Tab("資料來源管理"):
            gr.HTML("<h2>添加參考資料</h2>")
            with gr.Row():
                with gr.Column(scale=1):
                    file_input = gr.File(label="上傳檔案")
                    url_input = gr.Textbox(
                        label="輸入URL",
                        placeholder="https://..."
                    )
                    add_source_btn = gr.Button("添加資料來源")

                with gr.Column(scale=1):
                    sources_status = gr.Textbox(
                        label="已添加的資料來源",
                        interactive=False,
                        lines=10
                    )

    # 儲存對話狀態
    state = gr.State([])

    # 處理用戶輸入
    msg.submit(
        process_message,
        [msg, state, chatbot, agent_state],
        [msg, state, chatbot, preview]
    )

    # 處理資料來源添加
    add_source_btn.click(
        handle_source,
        [file_input, url_input, sources_status, agent_state],
        [sources_status, file_input, url_input]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)