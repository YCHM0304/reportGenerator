import gradio as gr
import time

class Agent:
    def init(self):
        self.history = []

    def respond(self, message):
        # 這裡可以接入實際的agent邏輯
        response = f"Agent回應: {message}"
        return response

def process_message(message, history, chatbot, output):
    if not message:
        return "", history, output

    # 將用戶輸入的訊息添加到對話歷史中
    history.append({"role": "User", "content": message})

    # 模擬Agent回應
    bot = Agent()
    response = bot.respond(message)
    history.append({"role": "Agent", "content": response})

    # 更新對話框
    output = response

    return "", history, output

with gr.Blocks(css="#chatbot {height: 400px} #output {height: 400px}") as demo:
    with gr.Row():
        with gr.Column(scale=1):
            gr.HTML("<h2>與Agent對話</h2>")
            chatbot = gr.Chatbot(
                [],
                elem_id="chatbot",
                height=400,
                bubble_full_width=False,
            )
            msg = gr.Textbox(
                show_label=False,
                placeholder="輸入訊息...",
            )

        with gr.Column(scale=1):
            gr.HTML("<h2>輸出結果</h2>")
            output = gr.Textbox(
                show_label=False,
                placeholder="這裡將顯示處理後的結果...",
                elem_id="output",
                lines=15,
            )

    # 儲存對話狀態
    state = gr.State([])

    # 處理用戶輸入
    msg.submit(
        process_message,
        [msg, state, chatbot, output],
        [msg, state, output]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)