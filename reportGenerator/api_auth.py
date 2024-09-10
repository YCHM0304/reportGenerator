import concurrent.futures
import io
import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from logging.handlers import TimedRotatingFileHandler
from typing import Dict, List, Any, Optional

import akasha
import jwt
import requests
from bs4 import BeautifulSoup
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi import FastAPI, HTTPException, Depends, Header, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel
from PyPDF2 import PdfReader
from sqlalchemy import create_engine, Column, String, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

def custom_namer(default_name):
    base_filename, ext, date = default_name.split(".")
    return f"{base_filename}.{date}.{ext}"

def setup_logging(tz_offset=8):  # 默認為 UTC+8（台北時間）
    log_path = os.environ.get('LOG_PATH', '/app/logs/fastapi_backend.log')
    log_dir = os.path.dirname(log_path)

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger("fastapi_backend")
    logger.setLevel(logging.DEBUG)

    file_handler = TimedRotatingFileHandler(
        log_path,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    file_handler.namer = custom_namer

    class TimezoneFormatter(logging.Formatter):
        def converter(self, timestamp):
            return datetime.fromtimestamp(timestamp, timezone(timedelta(hours=tz_offset)))

        def formatTime(self, record, datefmt=None):
            dt = self.converter(record.created)
            if datefmt:
                s = dt.strftime(datefmt)
            else:
                s = dt.isoformat(timespec='milliseconds')
            return s

    formatter = TimezoneFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger

logger = setup_logging()

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
    report_topic: str
    main_sections: Dict[str, List[str]]
    links: List[str]
    openai_config: Optional[Dict[str, Any]]
    final_summary: Optional[bool] = True

class ReprocessContentRequest(BaseModel):
    command: str
    openai_config: Optional[Dict[str, Any]]
    links: Optional[List[str]]
    user_decision: Optional[bool] = None

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
            logger.error("Invalid token: Missing username")
            raise credentials_exception
    except jwt.PyJWTError:
        logger.error("Invalid token: PyJWTError")
        raise credentials_exception
    with get_db() as db:
        user = db.query(User).filter(User.username == username).first()
    if user is None:
        logger.error("Invalid token: User not found")
        raise credentials_exception
    return user

class ReportGenerator:
    def __init__(self, username: str):
        self.username = username
        self.final_result = {}
        self.report_config = {
            "report_topic": "",
            "main_sections": {},
            "links": []
        }
        self.model = "openai:gpt-4"
        self.openai_config = {}

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

    def generate_report(self, request: ReportRequest, reprocess: bool = False, more_info: str = None):
        if not more_info:
            self.report_config["report_topic"] = request.report_topic
            self.report_config["main_sections"] = request.main_sections.copy()
        self.report_config["links"] = request.links.copy()
        self.openai_config = request.openai_config or {}

        if not self.load_openai():
            raise HTTPException(status_code=400, detail="請提供OpenAI或Azure的API金鑰")

        result = {}
        self.QA = akasha.Doc_QA(model=self.model, max_doc_len=8000)
        self.summary = akasha.Summary(chunk_size=1000, max_doc_len=2000)

        def process_link(link, format_prompt):
            try:
                response = requests.get(link)
                response.raise_for_status()

                if link.lower().endswith('.pdf'):
                    # Handle PDF file
                    pdf_file = io.BytesIO(response.content)
                    pdf_reader = PdfReader(pdf_file)
                    texts = ""
                    for page in pdf_reader.pages:
                        texts += page.extract_text()
                else:
                    # Handle HTML content
                    soup = BeautifulSoup(response.content, 'html.parser')
                    texts = soup.get_text()

                summary = self.summary.summarize_articles(
                    articles=texts,
                    format_prompt=format_prompt,
                )
                logger.debug(f"Summary generated for link {link}: {summary}")
                return summary
            except requests.exceptions.RequestException as e:
                print(f"Error fetching content from {link}: {str(e)}")
                logger.error(f"Error fetching content from {link}: {str(e)}")
                return ""
            except Exception as e:
                print(f"Error processing content from {link}: {str(e)}")
                logger.error(f"Error processing content from {link}: {str(e)}")
                return ""

        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            for main_section, subsections in request.main_sections.items():
                format_prompt = f"以{request.report_topic}為主題，請你總結撰寫出與\"{main_section}\"相關的內容，其中需包含{subsections}，不需要結論，不需要回應要求。" + f"另外，{more_info}" if reprocess else ""
                logger.debug(f"Format prompt for main section '{main_section}': {format_prompt}")

                future_to_link = {executor.submit(process_link, link, format_prompt): link for link in request.links}
                main_section_contexts = []
                for future in concurrent.futures.as_completed(future_to_link):
                    link = future_to_link[future]
                    try:
                        summary = future.result()
                        if summary:
                            main_section_contexts.append(summary)
                    except Exception as exc:
                        print(f'{link} generated an exception: {exc}')
                        logger.error(f'{link} generated an exception: {exc}')

                if main_section_contexts:
                    logger.debug(f"Contexts for main section '{main_section}': {main_section_contexts}")
                    response = self.QA.ask_self(
                        prompt=f"將此內容以客觀角度進行融合，避免使用\"報告中提到\"相關詞彙，避免修改專有名詞，避免做出總結，避免重複內容，直接撰寫內容，避免回應要求。",
                        info=main_section_contexts,
                        model=self.model
                    )
                    logger.debug(f"Generated content for main section '{main_section}': {response}")
                    result[main_section] = response
                else:
                    logger.warning(f"No content generated for main section '{main_section}'")
                    result[main_section] = "無法獲取相關內容"

        previous_result = ""
        for value in result.values():
            previous_result += value
        if not reprocess:
            logger.debug(f"Generating content summary")
            result["內容摘要"] = self.summary.summarize_articles(
                articles=previous_result,
                format_prompt=f"將內容以{request.report_topic}為主題進行摘要，將用字換句話說，意思不變，不需要結論，不需要回應要求。",
                summary_len=500
            )
            logger.debug(f"Generated content summary: {result['內容摘要']}")
        total_time = time.time() - start_time
        self.final_result = result.copy()
        return self.final_result, total_time

    def generate_recommend_main_sections(self, request: ReportRequest):
        report_topic = request.report_topic
        self.openai_config = request.openai_config or {}
        if not self.load_openai():
            raise HTTPException(status_code=400, detail="請提供OpenAI或Azure的API金鑰")
        self.QA = akasha.Doc_QA(model=self.model, max_doc_len=8000)
        formatter = akasha.prompts.JSON_formatter_list(names=["主要部分", "次要部分"], types=["list", "list"], descriptions=["每個主要部分", "每個主要部分的多個次要部分"])
        JSON_prompt = akasha.prompts.JSON_formatter(formatter)
        try:
            logger.debug(f"Generating recommended main sections for report topic: {report_topic}")
            generated_main_sections = self.QA.ask_self(
                system_prompt=JSON_prompt,
                prompt=f"我想要寫一份報告，請以{report_topic}為主題，幫我制定四個或五個主要部分，其中每個主要部分都有其各自的次要部分，請參考以下範例，並回答。",
                info="""
                    範例:
                    [給定主題]
                    電池產業的發展趨勢
                    [回應範例]
                    全球電池市場概況

                    市場規模與增長趨勢
                    主要市場區域分析
                    主要企業概況

                    技術發展趨勢

                    鋰離子電池技術進展
                    固態電池技術
                    其他新興電池技術
                """,
                model=self.model
            )
            logger.debug(f"Generated recommended main sections: {generated_main_sections}")
        except Exception as e:
            logger.error(f"Error generating recommended main sections: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        return generated_main_sections

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
            if not self.report_config["report_topic"]:
                logger.warning(f"Report topic not found for user: {self.username}")
            if not self.report_config["main_sections"]:
                logger.warning(f"Main sections not found for user: {self.username}")
            if not self.report_config["links"]:
                logger.warning(f"Links not found for user: {self.username}")
            return True

    def delete_result(self):
        with get_db() as db:
            report = db.query(Report).filter(Report.username == self.username).first()
            if report:
                db.delete(report)
                db.commit()

    def reprocess_content(self, request: ReprocessContentRequest):
        if not self.final_result:
            raise HTTPException(status_code=400, detail="請先使用generate_report生成報告")

        self.openai_config = request.openai_config or {}
        if not self.load_openai():
            raise HTTPException(status_code=400, detail="請提供OpenAI或Azure的API金鑰")

        self.QA = akasha.Doc_QA(model=self.model, max_doc_len=8000)
        self.summary = akasha.Summary(chunk_size=1000, max_doc_len=2000)

        if self.final_result != {}:
            main_sections = [key for key in self.final_result.keys()]
            new_request = self.QA.ask_self(
                prompt=f"""使用者輸入了以下修改要求:
                    ----------------
                    {request.command}
                    ----------------
                    從我提供的報告中所有的主要部分和使用者的修改要求中找出使用者要求修改的部分為何，以及要如何修改。請按以下格式回覆:

                    修改部分: <修改部分>
                    修改內容: <修改內容>

                    注意事項:
                    1. 若修改要求中有錯別字或文法錯誤，但仍能理解要求，也請按上述格式回覆。

                    2. 若只有提出修改的要求，沒有指定要修改的部分，請回覆:
                    "不知道您想要修改哪一部分，請提供更多資訊"

                    3. 若無明確指定想要如何修改，請回覆:
                    "無法理解您的修改要求，請提供更多資訊"

                    4. 若用戶要求同時修改多個部分，請分別列出每個修改部分和相應的修改內容。

                    5. 如果對於修改要求有任何不確定之處，請明確指出並提出澄清問題。

                    6. 只要要求中沒有明確提到list中的任何元素，就回覆"不知道您想要修改哪一部分，請提供更多資訊"。

                    請根據以上指示處理修改要求。

                    例子:
                    假設給定的報告中的主要部分包含: 摘要, 前言, 方法, 結果, 討論, 結論

                    修改要求: "把摘要改成200字"
                    回覆:
                        修改部分: 摘要
                        修改內容: 改寫為200字
                    修改要求: "將結果部分的數據圖表更新為最新數據"
                    回覆:
                        修改部分: 結果
                        修改內容: 更新數據圖表為最新數據
                    修改要求: "在文獻回顧中加入Smith等人的研究"
                    回覆:
                        報告中無此部分，請確認後再提出修改要求
                    修改要求: "改正錯別字"
                    回覆:
                        不知道您想要修改哪一部分，請提供更多資訊
                    修改要求: "在方法部分加入實驗步驟，並在結果中呈現更多統計數據"
                    回覆:
                        修改部分: 方法
                        修改內容: 加入實驗步驟
                    修改要求: "把結論改得更好"
                    回覆:
                        無法理解您的修改要求，請提供更多資訊
                    修改要求: "在摘要中加入研究目的，並且把它改得更簡潔"
                    回覆:
                        修改部分: 摘要
                        修改內容: 加入研究目的並使整體更簡潔
                """,
                info=f"報告中包含以下主要部分: {', '.join(main_sections)}",
                model=self.model,
                verbose=True
            )

            try:
                main_section = new_request.split("修改部分: ")[1].split("\n修改內容: ")[0]
                mod_command = new_request.split("修改部分: ")[1].split("\n修改內容: ")[1]
                logger.debug(f"Reprocessing main section: {main_section}, with command: {mod_command}")
                if main_section in self.final_result:
                    previous_context = self.final_result[main_section]
                    if request.user_decision is not None:
                        modification = "y" if request.user_decision else "n"
                    else:
                        modification = self.QA.ask_self(
                            prompt=f"""判斷是否需要重新爬取資料
                                請根據修改要求和提供的內容,回覆 y、n 或 unknown:

                                修改要求:
                                ----------------
                                {mod_command}
                                ----------------

                                判斷標準:
                                - 需要加入新資料時,回覆 y
                                - 僅需修改現有內容時,回覆 n
                                - 修改要求與內容無關或無法判斷時,回覆 unknown

                                示例:
                                1. 需要重新爬取 (y):
                                修改要求: 加入非洲市場區域分析
                                提供內容: 台灣電池產業發展迅速,主要市場包括亞洲、美洲和歐洲

                                2. 不需重新爬取 (n):
                                修改要求: 刪除亞洲市場區域分析
                                提供內容: 台灣電池產業發展迅速,主要市場包括亞洲、美洲和歐洲

                                3. 無法判斷 (unknown):
                                修改要求: 加入非洲動物大遷徙資訊
                                提供內容: 台灣電池產業發展迅速,主要市場包括亞洲、美洲和歐洲

                                請根據以上標準,對給定的修改要求做出判斷。
                            """,
                            info=previous_context,
                            model=self.model,
                            verbose=True
                        )
                    logger.debug(f"Modification decision: {modification}")
                    if modification == "unknown":
                        raise HTTPException(
                            status_code=422,
                            detail={
                                "message": "無法判斷是否需要重新爬取資料",
                                "requires_user_input": True,
                                "input_type": "boolean",
                                "input_question": "是否需要從原文重新爬取資料?",
                                "main_section": main_section,
                                "mod_command": mod_command
                            }
                        )
                    if modification == "y":
                        if request.links and (request.links not in self.report_config["links"]):
                            self.report_config["links"] += request.links
                            print("Links added to report config")
                            print(self.report_config["links"])
                        if main_section == "內容摘要":
                            raise HTTPException(status_code=400, detail="內容摘要無法重新爬取資料")
                        new_response = self.generate_report(
                            ReportRequest(
                                report_topic=self.report_config["report_topic"],
                                main_sections={main_section: self.report_config["main_sections"][main_section]},
                                links=self.report_config["links"],
                                openai_config=self.openai_config
                            ),
                            reprocess=True,
                            more_info=mod_command
                        )[0][main_section]
                        new_response = self.QA.ask_self(
                            prompt=f"將給定的兩個內容進行比較，將兩者不同的部分進行融合，成為一個新的內容，不需要結論，不需要回應要求。",
                            info=previous_context + "\n---\n" + new_response,
                            model=self.model,
                            verbose=True
                        )
                    elif modification == "n":
                        new_response = self.QA.ask_self(
                            prompt=f"""
                                請根據以下指示修改給定內容：

                                1. 閱讀提供的原始內容和修改要求。

                                2. 若能達成修改要求：
                                - 直接輸出修改後的內容
                                - 不要加上"要求已達成"等類似說明

                                3. 若無法達成修改要求：
                                - 輸出 "無法達成要求，因此不做任何修改"
                                - 換行後重複輸出原始內容

                                4. 不要撰寫或添加任何未在原始內容中提及的新資訊

                                修改要求:
                                {mod_command}

                                範例1（無法達成要求）：
                                原始內容：台灣的電池產業發展迅速，主要市場區域包括亞洲、美洲和歐洲。
                                要求：加入非洲市場區域分析。
                                輸出：
                                無法達成要求，因此不做任何修改

                                台灣的電池產業發展迅速，主要市場區域包括亞洲、美洲和歐洲。

                                範例2（可以達成要求）：
                                原始內容：台灣的電池產業發展迅速，主要市場區域包括亞洲、美洲和歐洲。
                                要求：去除跟亞洲有關資料。
                                輸出：
                                台灣的電池產業發展迅速，主要市場區域包括美洲和歐洲。
                            """,
                            info=previous_context,
                            model=self.model,
                            verbose=True
                        )
                    else:
                        logger.error(f"Main section not found: {main_section}")
                        raise HTTPException(status_code=400, detail="無法確定是否需要重新爬取資料")

                    modification_result = {
                        "original_content": previous_context,
                        "modified_content": new_response,
                        "main_section": main_section
                    }
                    logger.debug(f"Modification result: {modification_result}")
                    return modification_result
                else:
                    raise HTTPException(status_code=400, detail=f"未找到指定的主要部分: {main_section}")
            except Exception as e:
                logger.error(f"Error during content reprocessing: {str(e)}")
                raise HTTPException(status_code=400, detail=str(e))

        return {
            "original_content": "...",
            "modified_content": "...",
            "main_section": "..."
        }

    def update_content(self, main_section: str, new_content: str):
        """
        更新報告中特定主要部分的內容並保存。
        """
        if main_section in self.final_result:
            self.final_result[main_section] = new_content
            self.save_result()
            return True
        return False


user_sessions: Dict[str, ReportGenerator] = {}

@app.post("/register", response_model=Token)
async def register_user(user: UserCreate):
    logger.info(f"Registration attempt for user: {user.username}")
    with get_db() as db:
        db_user = db.query(User).filter(User.username == user.username).first()
        if db_user:
            logger.warning(f"Registration failed: Username {user.username} already exists")
            raise HTTPException(status_code=400, detail="Username already registered")
        hashed_password = get_password_hash(user.password)
        new_user = User(username=user.username, hashed_password=hashed_password)
        db.add(new_user)
        db.commit()
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    logger.info(f"User {user.username} registered successfully")
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    logger.info(f"Login attempt for user: {form_data.username}")
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.warning(f"Login failed: Incorrect username or password for {form_data.username}")
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    logger.info(f"User {form_data.username} logged in successfully")
    return {"access_token": access_token, "token_type": "bearer"}

def get_report_generator(current_user: User = Depends(get_current_user)):
    if current_user.username not in user_sessions:
        user_sessions[current_user.username] = ReportGenerator(username=current_user.username)
    return user_sessions[current_user.username]

@app.post("/generate_report")
async def generate_report(request: ReportRequest, generator: ReportGenerator = Depends(get_report_generator)):
    logger.info(f"Generating report for user: {generator.username}")
    result, total_time = generator.generate_report(request, not request.final_summary)
    generator.save_result()
    total_time = "%.2f" % total_time
    logger.info(f"Report generated for user: {generator.username}. Total time: {total_time} seconds")
    return {"result": result, "total_time": total_time}

@app.post("/generate_recommend_main_sections")
async def generate_recommend_main_sections(request: ReportRequest, generator: ReportGenerator = Depends(get_report_generator)):
    logger.info(f"Generating recommended main sections for user: {generator.username}")
    result = generator.generate_recommend_main_sections(request)
    logger.info(f"Recommended main sections generated for user: {generator.username}")
    return {"result": result}

@app.get("/check_result")
async def check_result(generator: ReportGenerator = Depends(get_report_generator)):
    return {"result": generator.load_result()}

@app.get("/get_report")
async def get_report(generator: ReportGenerator = Depends(get_report_generator)):
    logger.info(f"Retrieving report for user: {generator.username}")
    if generator.load_result():
        result = generator.final_result
        logger.info(f"Report retrieved for user: {generator.username}")
        return {"result": result}
    else:
        logger.error(f"Report not found for user: {generator.username}")
        raise HTTPException(status_code=400, detail="報告尚未生成")

@app.post("/save_reprocessed_content")
async def save_reprocessed_content(
    main_section: str = Body(...),
    new_content: str = Body(...),
    generator: ReportGenerator = Depends(get_report_generator)
):
    logger.info(f"Updating content for user: {generator.username}")
    if generator.update_content(main_section, new_content):
        logger.info(f"Content updated and saved for user: {generator.username}")
        return {"result": "Content updated and saved successfully"}
    else:
        logger.error(f"Failed to update content for user: {generator.username}")
        raise HTTPException(status_code=400, detail="無法更新指定的主要部分")

@app.get("/download_report")
async def download_report(generator: ReportGenerator = Depends(get_report_generator)):
    logger.info(f"Generating downloadable report for user: {generator.username}")
    if generator.load_result():
        result = generator.final_result

        # Generate report content
        report_content = io.StringIO()
        report_content.write(f"Report for: {generator.report_config['report_topic']}\n\n")

        for main_section, content in result.items():
            report_content.write(f"# {main_section}\n\n")
            report_content.write(f"{content}\n\n")

        # Create a StreamingResponse
        response = StreamingResponse(iter([report_content.getvalue()]), media_type="text/plain")
        response.headers["Content-Disposition"] = f"attachment; filename=report_{generator.username}.txt"

        logger.info(f"Downloadable report generated for user: {generator.username}")
        return response
    else:
        logger.error(f"Report not found for user: {generator.username}")
        raise HTTPException(status_code=400, detail="報告尚未生成")

@app.post("/reprocess_content")
async def reprocess_content(
    request: ReprocessContentRequest,
    generator: ReportGenerator = Depends(get_report_generator)
):
    logger.info(f"Reprocessing content for user: {generator.username}")
    generator.load_result()
    try:
        result = generator.reprocess_content(request)
        logger.info(f"Content reprocessed for user: {generator.username}")
        return {"result": result}
    except HTTPException as e:
        if e.status_code == 422:
            return JSONResponse(status_code=422, content=e.detail)
        raise e

@app.get("/logout")
async def logout(generator: ReportGenerator = Depends(get_report_generator)):
    logger.info(f"User {generator.username} logged out")
    if generator.username in user_sessions:
        del user_sessions[generator.username]
    return {"result": "Logged out"}

@app.delete("/delete_report")
async def delete_report(generator: ReportGenerator = Depends(get_report_generator)):
    logger.info(f"User {generator.username} logged out and report deleted")
    generator.delete_result()
    if generator.username in user_sessions:
        del user_sessions[generator.username]
    return {"result": "Logged out and report deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)