import akasha
import re

with open('./result/電池報告4.txt', 'r', encoding='utf-8') as file:
    data = file.read()

pattern = re.compile(r"(內容摘要:|產業範圍:|產業發展動向:|企業動態:|企業前瞻:)")

# Split the text by the titles
split_text = pattern.split(data)

split_text.pop(0)

print(split_text)


QA = akasha.Doc_QA()
tmp = []
response = split_text[0] + split_text[1]

for texts in split_text:
    if len(tmp) < 4:
        tmp.append(texts)
    else:
        print("----------------")
        print(tmp)
        print("----------------")
        response += QA.ask_self(
            f"修飾文句，將{tmp[2]}中與{tmp[0]}有重複的部分移除，只保留{tmp[2]}的標題及內容",
            max_doc_len = 1000,
            info = tmp[0] + tmp[1] + tmp[2] + tmp[3],
            model = "openai:gpt-4"
        )
        for _ in range(2):
            tmp.pop(0)
        tmp.append(texts)

print("-----------------")
print(response)