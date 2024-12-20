from threading import local
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import akasha
import requests
import os
from bs4 import BeautifulSoup
import uuid
import json
import time
import concurrent.futures

app = FastAPI()
thread_local = local()

class ReportRequest(BaseModel):
    theme: str
    titles: Dict[str, List[str]]
    links: List[str]
    openai_config: Optional[Dict[str, Any]]

class ReprocessContentRequest(BaseModel):
    command: str
    openai_config: Optional[Dict[str, Any]]

# 定義 request model
class ReportGenerator:
    def __init__(self, session_id: str=""):
        self.final_result = {}
        self.report_config = {
            "theme": "",
            "titles": {},
            "links": []
        }
        self.model = "openai:gpt-4"
        self.openai_config = {}
        self.session_id = session_id

    def load_openai(self) -> bool:
        # 刪除舊的環境變量
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        if "AZURE_API_BASE" in os.environ:
            del os.environ["AZURE_API_BASE"]
        if "AZURE_API_KEY" in os.environ:
            del os.environ["AZURE_API_KEY"]
        if "AZURE_API_TYPE" in os.environ:
            del os.environ["AZURE_API_TYPE"]
        if "AZURE_API_VERSION" in os.environ:
            del os.environ["AZURE_API_VERSION"]

        # 設置 OpenAI API 密鑰
        config = self.openai_config
        if "openai_key" in config and config["openai_key"]:
            os.environ["OPENAI_API_KEY"] = config["openai_key"]
            return True
        if "azure_key" in config and "azure_base" in config and config["azure_key"] and config["azure_base"]:
            os.environ["AZURE_API_KEY"] = config["azure_key"]
            os.environ["AZURE_API_BASE"] = config["azure_base"]
            os.environ["AZURE_API_TYPE"] = "azure"
            os.environ["AZURE_API_VERSION"] = "2023-05-15"
            print("Azure API Key: ", os.environ["AZURE_API_KEY"])
            print("Azure API Base: ", os.environ["AZURE_API_BASE"])
            return True
        return False

    def generate_report(self, request: ReportRequest):
        self.report_config["theme"] = request.theme
        self.report_config["titles"] = request.titles.copy()
        self.report_config["links"] = request.links.copy()
        self.openai_config = request.openai_config or {}

        if not self.load_openai():
            raise HTTPException(status_code=400, detail="請提供OpenAI或Azure的API金鑰")

        result = {}
        contexts = []
        self.QA = akasha.Doc_QA(model=self.model, max_doc_len=8000)
        self.summary = akasha.Summary(chunk_size=1000, max_doc_len=7000)

        def process_title(title, subtitle):
            format_prompt = f"以{request.theme}為主題，請你總結撰寫出與\"{title}\"相關的內容，其中需包含{subtitle}，不需要結論，不需要回應要求。"
            title_contexts = []
            for link in request.links:
                try:
                    response = requests.get(link)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    texts = soup.get_text()
                except requests.exceptions.RequestException as e:
                    raise HTTPException(status_code=400, detail=f"Error fetching content: {str(e)}")

                title_contexts.append(
                    self.summary.summarize_articles(
                        articles=texts,
                        format_prompt=format_prompt,
                    )
                )

            response = self.QA.ask_self(
                prompt=f"將此內容以客觀角度進行融合，避免使用\"報告中提到\"相關詞彙，避免修改專有名詞，避免做出總結，直接撰寫內容，避免回應要求。",
                info=title_contexts,
                model="openai:gpt-4"
            )
            return title, response

        # 使用線程池處理每個標題
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_title = {executor.submit(process_title, title, subtitle): title for title, subtitle in request.titles.items()}
            for future in concurrent.futures.as_completed(future_to_title):
                title = future_to_title[future]
                try:
                    title, response = future.result()
                    result[title] = response
                except Exception as exc:
                    print(f'{title} generated an exception: {exc}')

        # 生成內容摘要
        previous_result = ""
        for value in result.values():
            previous_result += value

        result["內容摘要"] = self.summary.summarize_articles(
            articles=previous_result,
            format_prompt=f"將內容以{request.theme}為主題進行摘要，將用字換句話說，意思不變，不需要結論，不需要回應要求。",
            summary_len=500
        )
        total_time = time.time() - start_time
        self.final_result = result.copy()
        return self.final_result, total_time

    def save_result(self, save_path: str="./result.json"):
        # 檢查文件是否存在
        if os.path.exists(save_path):
            # 如果文件存在，先讀取現有的數據
            with open(save_path, "r") as f:
                existing_data = json.load(f)
        else:
            # 如果文件不存在，創建一個空字典
            existing_data = {}

        # 將新的結果加入到現有數據中
        existing_data[self.session_id] = {"final_result": self.final_result, "report_config": self.report_config}

        # 將更新後的數據寫入文件
        with open(save_path, "w") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)

    def load_result(self, load_path: str="./result.json"):
        # 檢查文件是否存在
        if os.path.exists(load_path):
            # 如果文件存在，先讀取現有的數據
            with open(load_path, "r") as f:
                existing_data = json.load(f)
            self.final_result = existing_data[self.session_id]["final_result"]
            self.report_config = existing_data[self.session_id]["report_config"]
            if not self.final_result:
                return False
            if not self.report_config["theme"]:
                return False
            if not self.report_config["titles"]:
                return False
            if not self.report_config["links"]:
                return False
            return True
        else:
            return False

    def delete_result(self, delete_path: str="./result.json"):
        # 檢查文件是否存在
        if os.path.exists(delete_path):
            # 如果文件存在，先讀取現有的數據
            with open(delete_path, "r") as f:
                existing_data = json.load(f)
            # 刪除指定的會話
            existing_data.pop(self.session_id)
            # 將更新後的數據寫入文件
            with open(delete_path, "w") as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=4)

    def reprocess_content(self, request: ReprocessContentRequest):
         # 重新處理內容
        if not self.final_result:
            raise HTTPException(status_code=400, detail="请先使用generate_report生成报告")
        if self.final_result != {}:
            # 使用 QA 模型解析用戶的修改要求
            new_request= self.QA.ask_self(
                prompt=f"""使用者輸入了以下修改要求:
                ----------------
                {request.command}
                ----------------
                從給定的list和使用者的修改要求中找出使用者要求修改的部分為何，以及要如何修改，前面不須加上"回覆:"。

                範例:
                <給定的list>
                ["全球電池市場概況", "技術發展趨勢", "應用領域與市場機會", "政策與供應鏈分析"]
                <要求>
                技術發展趨勢的部分我覺得不夠完整，請加入更多新興電池技術的內容。
                <回覆>
                修改部分: 技術發展趨勢
                修改內容: 加入更多新興電池技術的內容

                若要求的部分不在給定的list當中，請回覆"報告中無此部分，請確認後再提出修改要求"，前面不須加上"回覆:"。

                範例:
                <給定的list>
                ["全球電池市場概況", "技術發展趨勢", "應用領域與市場機會", "政策與供應鏈分析"]
                <要求>
                我覺得電池發展歷史的部分不夠完整，請幫我修改。
                <回覆>
                報告中無此部分，請確認後再提出修改要求。

                若修改要求中雖然有錯別字或文法錯誤，但仍能理解要求，也請回覆"修改部分: <修改部分> 修改內容: <修改內容>"，前面不須加上"回覆:"。

                範例:
                <給定的list>
                ["全球電池市場概況", "技術發展趨勢", "應用領域與市場機會", "政策與供應鏈分析"]
                <要求>
                我覺得全球電池試場概況的部分不夠完整，請加入更多市場規模與增長趨勢的內容。
                <回覆>
                修改部分: 全球電池市場概況
                修改內容: 加入更多市場規模與增長趨勢的內容

                若只有提出修改的要求，沒有指定要修改的部分，請回覆"不知道您想要修改哪一部分，請提供更多資訊"。避免自動回覆list中所有項目。前面不須加上"回覆:"。
                只要要求中沒有看到list中的element，就回覆"不知道您想要修改哪一部分，請提供更多資訊"。
                範例:
                <給定的list>
                ["全球電池市場概況", "技術發展趨勢", "應用領域與市場機會", "政策與供應鏈分析"]
                <要求>
                去除2025年以前的資料。
                <回覆>
                不知道您想要修改哪一部分，請提供更多資訊

                若無明確指定想要如何修改，回覆"無法理解您的修改要求，請提供更多資訊"，前面不須加上"回覆:"。

                <給定的list>
                ["全球電池市場概況", "技術發展趨勢", "應用領域與市場機會", "政策與供應鏈分析"]
                <要求>
                我覺得技術發展趨勢的部分有問題。
                <回覆>
                無法理解您的修改要求，請提供更多資訊
                """,
                info=[key for key in self.final_result.keys()],
                model="openai:gpt-4"
            )

            try:
                # 解析修改請求
                part = new_request.split("修改部分: ")[1].split("\n修改內容: ")[0]
                mod_command = new_request.split("修改部分: ")[1].split("\n修改內容: ")[1]
                if part in self.final_result:
                    previous_context = self.final_result[part]
                    # 判斷是否需要重新爬取資料
                    modification = self.QA.ask_self(
                        prompt=f"""從以下修改要求和提供的內容判斷是否需要重新爬取資料。大部分情況需要加入新的資料進去時會，
                        需要爬取資料，此時需要回覆"y"。否則回覆"n"。若修改要求和提供的內容完全沒有關聯性或者無法判斷時，請回覆"unknown"。
                        ----------------
                        {mod_command}
                        ----------------
                        y的範例:
                        <修改要求>
                        加入非洲市場區域分析。
                        <提供的內容>
                        台灣的電池產業發展迅速，主要市場區域包括亞洲、美洲和歐洲。
                        <回覆>
                        y

                        n的範例:
                        <修改要求>
                        消去亞洲市場區域分析。
                        <提供的內容>
                        台灣的電池產業發展迅速，主要市場區域包括亞洲、美洲和歐洲。
                        <回覆>
                        n

                        unknown的範例:
                        <修改要求>
                        加入非洲動物大遷徙的資訊
                        <提供的內容>
                        台灣的電池產業發展迅速，主要市場區域包括亞洲、美洲和歐洲。
                        <回覆>
                        unknown
                        """,
                        info=previous_context,
                        model="openai:gpt-4"
                    )
                    # 處理修改請求
                    while modification == "unknown":
                        modification = input("無法判斷是否需要重新爬取資料，請問是否需要從原文重新爬取資料? (y/n)\n")
                        if modification != "y" and modification != "n":
                            modification = "unknown"
                    if modification == "y":
                        new_response = generate_report(theme=self.report_config["theme"], titles={part:[self.report_config["titles"][part]]}, links=self.report_config["links"], rerun_process=True)
                    elif modification == "n":
                        new_response =self.QA.ask_self(
                            prompt=f"""將此內容根據以下要求進行修改，若無法達成則不要修改任何內容直接輸出原始內容，不要亂撰寫內容:
                            ----------------
                            {mod_command}
                            ----------------

                            範例:
                            <原始內容>
                            台灣的電池產業發展迅速，主要市場區域包括亞洲、美洲和歐洲。
                            <要求>
                            加入非洲市場區域分析。
                            (無法達成)
                            <修改後內容>
                            "無法達成要求，因此不做任何修改"
                            \n\n
                            台灣的電池產業發展迅速，主要市場區域包括亞洲、美洲和歐洲。(輸出與原始內容相同的內容)

                            若能順利修改，則直接輸出修改後的內容，不需要加上類似"要求已達成"這句話。

                            範例:
                            <原始內容>
                            台灣的電池產業發展迅速，主要市場區域包括亞洲、美洲和歐洲。
                            <要求>
                            去除跟亞洲有關資料。
                            <修改後內容>
                            台灣的電池產業發展迅速，主要市場區域包括美洲和歐洲。
                            """,
                            info=previous_context,
                            model="openai:gpt-4"
                        )
                    else:
                        raise HTTPException(status_code=400, detail="無法確定是否需要重新爬取資料")

                    return {
                        "original_content": previous_context,
                        "modified_content": new_response,
                        "part": part
                    }
                else:
                    raise HTTPException(status_code=400, detail=f"未找到指定的部分: {part}")
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        return {
            "original_content": "...",
            "modified_content": "...",
            "part": "..."
        }

user_sessions: Dict[str, ReportGenerator] = {}

# 獲取報告生成器的依賴函數
def get_report_generator(session_id: str = Header(alias="session_id", default=None)):
    if session_id is None:
        session_id = str(uuid.uuid4())
    if session_id not in user_sessions:
        user_sessions[session_id] = ReportGenerator(session_id=session_id)
    return user_sessions[session_id], session_id

# API 路由
@app.post("/generate_report")
async def generate_report(request: ReportRequest, session_data: tuple = Depends(get_report_generator)):
    """生成報告的 API 端點"""
    generator, session_id = session_data
    result, total_time = generator.generate_report(request)
    generator.save_result()
    return {"session_id": session_id, "result": result, "total_time": total_time}


@app.get("/check_result")
async def check_result(session_data: tuple = Depends(get_report_generator)):
    """檢查報告結果的 API 端點"""
    generator, session_id = session_data
    return {"session_id": session_id, "result": generator.load_result()}

@app.get("/get_report")
async def get_report(session_data: tuple = Depends(get_report_generator)):
    """獲取報告的 API 端點"""
    generator, session_id = session_data
    if generator.load_result():
        result = generator.final_result
        return {"session_id": session_id, "result": result}
    else:
        raise HTTPException(status_code=400, detail="報告尚未生成")


@app.post("/reprocess_content")
async def reprocess_content(request: ReprocessContentRequest, session_data: tuple = Depends(get_report_generator)):
    """重新處理內容的 API 端點"""
    generator, session_id = session_data
    generator.load_result()
    result = generator.reprocess_content(request)
    return {"session_id": session_id, "result": result}

@app.delete("/delete_session")
async def delete_session(session_data: tuple = Depends(get_report_generator)):
    """刪除會話的 API 端點"""
    generator, session_id = session_data
    generator.delete_result()
    del user_sessions[session_id]
    return {"session_id": session_id, "result": "Session deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)