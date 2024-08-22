from fastapi import FastAPI, HTTPException, Depends, Header, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import akasha
import requests
import os
from bs4 import BeautifulSoup
import json
import time
import concurrent.futures
from sqlalchemy import create_engine, Column, String, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta, timezone

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://reportuser:report_password@localhost/reportdb")
engine = create_engine(DATABASE_URL)
Base = declarative_base()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = "report_secret_key"  # In production, use a secure secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class User(Base):
    __tablename__ = 'users'

    username = Column(String, primary_key=True)
    hashed_password = Column(String)

class Report(Base):
    __tablename__ = 'reports'

    username = Column(String, primary_key=True)
    final_result = Column(JSON)
    report_config = Column(JSON)

Base.metadata.create_all(engine)

SessionLocal = sessionmaker(bind=engine)

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class UserCreate(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class ReportRequest(BaseModel):
    theme: str
    titles: Dict[str, List[str]]
    links: List[str]
    openai_config: Optional[Dict[str, Any]]

class ReprocessContentRequest(BaseModel):
    command: str
    openai_config: Optional[Dict[str, Any]]

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(username: str, password: str):
    with get_db() as db:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return False
        if not verify_password(password, user.hashed_password):
            return False
        return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    with get_db() as db:
        user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

class ReportGenerator:
    def __init__(self, username: str):
        self.username = username
        self.final_result = {}
        self.report_config = {
            "theme": "",
            "titles": {},
            "links": []
        }
        self.model = "openai:gpt-4"
        self.openai_config = {}
        self.QA = akasha.Doc_QA(model=self.model, max_doc_len=8000)
        self.summary = akasha.Summary(chunk_size=1000, max_doc_len=7000)


    def load_openai(self) -> bool:
        # Delete old environment variables
        for key in ["OPENAI_API_KEY", "AZURE_API_BASE", "AZURE_API_KEY", "AZURE_API_TYPE", "AZURE_API_VERSION"]:
            if key in os.environ:
                del os.environ[key]

        # Set OpenAI API key
        config = self.openai_config
        if "openai_key" in config and config["openai_key"]:
            os.environ["OPENAI_API_KEY"] = config["openai_key"]
            return True
        if "azure_key" in config and "azure_base" in config and config["azure_key"] and config["azure_base"]:
            os.environ["AZURE_API_KEY"] = config["azure_key"]
            os.environ["AZURE_API_BASE"] = config["azure_base"]
            os.environ["AZURE_API_TYPE"] = "azure"
            os.environ["AZURE_API_VERSION"] = "2023-05-15"
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
        self.QA = akasha.Doc_QA(model=self.model, max_doc_len=8000)
        self.summary = akasha.Summary(chunk_size=1000, max_doc_len=7000)

        def process_link(link, format_prompt):
            try:
                response = requests.get(link)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                texts = soup.get_text()
                return self.summary.summarize_articles(
                    articles=texts,
                    format_prompt=format_prompt,
                )
            except requests.exceptions.RequestException as e:
                print(f"Error fetching content from {link}: {str(e)}")
                return ""

        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            for title, subtitle in request.titles.items():
                format_prompt = f"以{request.theme}為主題，請你總結撰寫出與\"{title}\"相關的內容，其中需包含{subtitle}，不需要結論，不需要回應要求。"

                future_to_link = {executor.submit(process_link, link, format_prompt): link for link in request.links}
                title_contexts = []
                for future in concurrent.futures.as_completed(future_to_link):
                    link = future_to_link[future]
                    try:
                        summary = future.result()
                        if summary:
                            title_contexts.append(summary)
                    except Exception as exc:
                        print(f'{link} generated an exception: {exc}')

                if title_contexts:
                    response = self.QA.ask_self(
                        prompt=f"將此內容以客觀角度進行融合，避免使用\"報告中提到\"相關詞彙，避免修改專有名詞，避免做出總結，避免重複內容，直接撰寫內容，避免回應要求。",
                        info=title_contexts,
                        model="openai:gpt-4"
                    )
                    result[title] = response
                else:
                    result[title] = "無法獲取相關內容"

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

    def save_result(self):
        with get_db() as db:
            report = Report(
                username=self.username,
                final_result=self.final_result,
                report_config=self.report_config
            )
            db.merge(report)
            db.commit()

    def load_result(self):
        with get_db() as db:
            report = db.query(Report).filter(Report.username == self.username).first()
            if report:
                self.final_result = report.final_result
                self.report_config = report.report_config
            if not self.final_result:
                return False
            if not self.report_config["theme"]:
                return False
            if not self.report_config["titles"]:
                return False
            if not self.report_config["links"]:
                return False
            return True

    def delete_result(self):
        with get_db() as db:
            report = db.query(Report).filter(Report.username == self.username).first()
            if report:
                db.delete(report)
                db.commit()

    def reprocess_content(self, request: ReprocessContentRequest):
        if not self.final_result:
            raise HTTPException(status_code=400, detail="请先使用generate_report生成报告")
        if not self.load_openai():
            raise HTTPException(status_code=400, detail="請提供OpenAI或Azure的API金鑰")

        self.QA = akasha.Doc_QA(model=self.model, max_doc_len=8000)
        self.summary = akasha.Summary(chunk_size=1000, max_doc_len=7000)

        if self.final_result != {}:
            new_request = self.QA.ask_self(
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
                part = new_request.split("修改部分: ")[1].split("\n修改內容: ")[0]
                mod_command = new_request.split("修改部分: ")[1].split("\n修改內容: ")[1]
                if part in self.final_result:
                    previous_context = self.final_result[part]
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
                    while modification == "unknown":
                        modification = input("無法判斷是否需要重新爬取資料，請問是否需要從原文重新爬取資料? (y/n)\n")
                        if modification != "y" and modification != "n":
                            modification = "unknown"
                    if modification == "y":
                        new_response = self.generate_report(
                            ReportRequest(
                                theme=self.report_config["theme"],
                                titles={part: [self.report_config["titles"][part]]},
                                links=self.report_config["links"],
                                openai_config=self.openai_config
                            )
                        )[0]
                    elif modification == "n":
                        new_response = self.QA.ask_self(
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

    def update_content(self, part: str, new_content: str):
        """
        更新報告中特定部分的內容並保存。
        """
        if part in self.final_result:
            self.final_result[part] = new_content
            self.save_result()
            return True
        return False


user_sessions: Dict[str, ReportGenerator] = {}

@app.post("/register", response_model=Token)
async def register_user(user: UserCreate):
    with get_db() as db:
        db_user = db.query(User).filter(User.username == user.username).first()
        if db_user:
            raise HTTPException(status_code=400, detail="Username already registered")
        hashed_password = get_password_hash(user.password)
        new_user = User(username=user.username, hashed_password=hashed_password)
        db.add(new_user)
        db.commit()
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

def get_report_generator(current_user: User = Depends(get_current_user)):
    if current_user.username not in user_sessions:
        user_sessions[current_user.username] = ReportGenerator(username=current_user.username)
    return user_sessions[current_user.username]

@app.post("/generate_report")
async def generate_report(request: ReportRequest, generator: ReportGenerator = Depends(get_report_generator)):
    result, total_time = generator.generate_report(request)
    generator.save_result()
    return {"result": result, "total_time": total_time}

@app.get("/check_result")
async def check_result(generator: ReportGenerator = Depends(get_report_generator)):
    return {"result": generator.load_result()}

@app.get("/get_report")
async def get_report(generator: ReportGenerator = Depends(get_report_generator)):
    if generator.load_result():
        result = generator.final_result
        return {"result": result}
    else:
        raise HTTPException(status_code=400, detail="報告尚未生成")

# Add a new API endpoint
@app.post("/save_reprocessed_content")
async def save_reprocessed_content(
    part: str = Body(...),
    new_content: str = Body(...),
    generator: ReportGenerator = Depends(get_report_generator)
):
    if generator.update_content(part, new_content):
        return {"result": "Content updated and saved successfully"}
    else:
        raise HTTPException(status_code=400, detail="無法更新指定的部分")

@app.post("/reprocess_content")
async def reprocess_content(request: ReprocessContentRequest, generator: ReportGenerator = Depends(get_report_generator)):
    generator.load_result()
    result = generator.reprocess_content(request)
    return {"result": result}

@app.delete("/delete_report")
async def delete_report(generator: ReportGenerator = Depends(get_report_generator)):
    generator.delete_result()
    del user_sessions[generator.username]
    return {"result": "Report deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)