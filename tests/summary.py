import akasha
import os
import PyPDF2


model = "openai:gpt-4o"
result = {}
response = ""
QA = akasha.Doc_QA(model=model, max_doc_len=5000)

summary = akasha.Summary(chunk_size=1000)
system_prompt = "你是一個非常擅長寫報告的電池產業專業人員，你會根據指定的格式來生成報告，且內容會完全符合指定的主題。若你無法回答會告訴我原因。"


titles = ["內容摘要", "企業範圍", "產業發展動向", "企業動態", "企業前瞻"]
contexts = []
report = {}


for title in titles:
    format_prompt = f"以電池產業發展的趨勢為主題，以\"{title}\"為標題撰寫出對應內容，不需要結論。"
    title_summaries = []
    for file_name in os.listdir('doc'):
        if os.path.isfile(os.path.join('doc', file_name)):
            print("##################################")
            print("Loading file name: ", file_name)
            print("##################################")

            with open(os.path.join('doc', file_name), 'rb') as file:
                texts = ""
                if file_name.endswith('.pdf'):
                    pdf = PyPDF2.PdfReader(file)
                    for page_num in range(len(pdf.pages)):
                        page = pdf.pages[page_num]
                        texts += page.extract_text()
                elif file_name.endswith('.txt'):
                    texts = file.read().decode('utf-8')

            contexts.append(
                summary.summarize_articles(
                    texts,
                    summary_len=250,
                    system_prompt=system_prompt,
                    format_prompt=format_prompt,
                )
            )

    response = QA.ask_self(
        prompt=f"將此內容以\"{title}\"為主題進行整合，以客觀角度撰寫，避免使用\"報告中提到\"相關詞彙，避免修改專有名詞，避免做出總結。",
        info=contexts,
        model="openai:gpt-4"
    )
    result[title] = response
    
    print(f"----------integrated summary of {title}----------")
    print(response + "\n")


print("----------Complete report----------")
for key, value in result.items():
    print(key, ":\n\t", value)

