import akasha
from akasha.akashas import atman, Doc_QA
from akasha.summary import Summary
import akasha.prompts as prompts
from akasha.db import RecursiveCharacterTextSplitter
import os

DEFAULT_REPORT_FORMAT = {
    "起": {},
    "承": {},
    "轉": {},
    "和": {},
}
DEFAULT_SUMMARY_FORMAT = prompts.JSON_formatter_dict(
    [
        {"name": "標題1", "description": "第一個標題和內文", "type": "str"},
        {"name": "標題2", "description": "第二個標題和內文", "type": "str"},
        {"name": "標題3", "description": "第三個標題和內文", "type": "str"},
        {"name": "標題4", "description": "第四個標題和內文", "type": "str"}
    ]
)


class ReportGenerator(atman):
    def __init__(
            self,
            report_format=DEFAULT_REPORT_FORMAT
    ):
        self.report_format = report_format
        self.summary = akasha.Summary()

    def _chunk_splitter(self, text):
        text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n", " ", ",", ".", "。", "!"],
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        split_chunk = text_splitter.split_text(text)
        return split_chunk

    @staticmethod
    def _summarize_and_generate_headings(dir_path, format_prompt="", formatter=DEFAULT_SUMMARY_FORMAT):
        sum_tool = Summary()
        qa = Doc_QA()
        final_sum = ""
        json_prompt = prompts.JSON_formatter(formatter=formatter)
        for file_name in os.listdir('doc'):
            if os.path.isfile(os.path.join('doc', file_name)):
                print("##################################")
                print("Processing summarization and heading of ", file_name)
                print("##################################")
                tmp_sum = sum_tool.summarize_file(
                    dir_path,
                    system_prompt=json_prompt,
                    format_prompt=format_prompt
                )
                # tmp_sum = summarization_with_heading = qa.ask_self(
                #     info=tmp_sum,
                #     prompt="依照內文加上相對應的標題，嚴格遵守格式如下:\n\t<標題>:\n\t\t<內文>\n\t<標題>:\n\t\t<內文>\n...",
                # )
                final_sum += tmp_sum
        return final_sum
    
    def _get_content(self, file_path):
        print("##################################")
        print("Loading file name: ", os.path.basename(file_path))
        print("##################################")
        documents = akasha.db._load_file(file_path=file_path, extension=file_path.split(".")[-1])
        text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n", " ", ",", ".", "。", "!"],
            chunk_size=self.summary.chunk_size, 
            chunk_overlap=self.summary.chunk_overlap,
        )
        docs = text_splitter.split_documents(documents)
        self.summary.doc_length = akasha.helper.get_docs_length(self.summary.language, docs)
        return [doc.page_content for doc in docs]

    def _single_file_title_summary(self, theme, title, texts):
        system_prompt = "你是一個非常擅長寫報告的電池產業專業人員，你會根據指定的格式來生成報告，且內容會完全符合指定的主題。若你無法回答會告訴我原因。"
        format_prompt = f"以\"{theme}\"為主題，以\"{title}\"為標題生成對應內容，不需要結論。"
        sum = self.summary.summarize_articles(
            texts,
            summary_len=250,
            system_prompt=system_prompt,
            format_prompt=format_prompt,
        )
        return sum

    def _final_title_summary(self, theme, texts):
        QA = Doc_QA()
        response = QA.ask_self(
            prompt=f"將此內容以\"{theme}\"為主題進行整合，以客觀角度撰寫，避免使用\"報告中提到\"相關詞彙，避免修改專有名詞，避免做出總結，\
                        生出約 250 字的報告。",
            info=texts,
            model="openai:gpt-4"
        )
        print(f"----------integrated summary----------")
        print(response + "\n")
        return response
    
    def generate_report(self, theme, titles, dir_path):
        report = {}
        for title in titles:
            title_summaries = []
            for file_name in os.listdir(dir_path):
                if os.path.isfile(os.path.join(dir_path, file_name)):
                    texts = self._get_content(os.path.join(dir_path, file_name))
                    title_summaries.append(
                        self._single_file_title_summary(
                            theme,
                            title,
                            texts
                        )
                    )
                    report[title] = self._final_title_summary(theme, title_summaries)
        return report
    
if __name__ == "__main__":
    report_gen = ReportGenerator()
    print(report_gen.generate_report("電池產業發展的趨勢", ["內容摘要", "企業範圍", "產業發展動向", "企業動態", "企業前瞻"], "doc"))
