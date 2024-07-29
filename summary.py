import akasha
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--mode", type=str, default="內容摘要")

args = parser.parse_args()

model = "openai:gpt-4o"
result = ""
response = ""
QA = akasha.Doc_QA(model=model, max_doc_len=5000)

summary = akasha.Summary(chunk_size=1000)
system_prompt = "你是一個非常擅長寫報告的電池產業專業人員，你會根據指定的格式來生成報告，且內容會完全符合指定的主題。若你無法回答會告訴我原因。"

contexts = []
format_prompt = f"以電池產業發展的趨勢為主題，以\"{args.mode}\"為標題生成對應內容，不需要結論。\""
for file_name in os.listdir('doc'):
    if os.path.isfile(os.path.join('doc', file_name)):
        print("##################################")
        print("Loading file name: ", file_name)
        print("##################################")

        documents = akasha.db._load_file(os.path.join('doc', file_name), file_name.split(".")[-1])
        text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n", " ", ",", ".", "。", "!"],
            chunk_size=summary.chunk_size,
            chunk_overlap=summary.chunk_overlap,
        )
        docs = text_splitter.split_documents(documents)
        summary.doc_length = akasha.helper.get_docs_length(summary.language, docs)
        texts = [doc.page_content for doc in docs]
        contexts.append(
            summary.summarize_articles(
                texts,
                summary_len=250,
                system_prompt=system_prompt,
                format_prompt=format_prompt,
            )
        )

    response = QA.ask_self(
        prompt=f"將此內容以\"{args.mode}\"為主題進行整合，以客觀角度撰寫，避免使用\"報告中提到\"相關詞彙，避免修改專有名詞，避免做出總結，\
                    生出約 250 字的報告。",
        info=contexts,
        model="openai:gpt-4"
    )
print(f"----------integrated summary of {args.mode}----------")
print(response + "\n")
result += response

print("-----------------")
print(result)
