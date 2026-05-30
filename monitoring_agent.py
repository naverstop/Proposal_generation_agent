import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import json
import os
import warnings
from urllib3.exceptions import InsecureRequestWarning
from dotenv import load_dotenv

load_dotenv()

# SSL 경고 메시지를 비활성화합니다.
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# --- LLM 관련 라이브러리 추가 ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- 설정 파일 관리 ---
CONFIG_FILE = 'agent_config.json'
AGENCIES_FILE = 'agencies.json'

def load_config():
    """에이전트 설정 파일(agent_config.json)을 읽어옵니다."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # 기본 설정 파일 생성
        default_config = {
            "execution_times": ["09:00", "17:00"],
            "recipients": ["user@example.com"],
            "crawling_keywords": ["AI", "인공지능", "데이터"],
            "report_template": "다음은 {agency_name}에서 수집된 최신 공고 목록입니다.\n각 공고의 핵심 내용을 분석하고, 우리 회사와의 관련성을 중심으로 3문장 이내로 요약 보고해주세요.\n\n{formatted_announcements}"
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)
        return default_config

def save_config(config):
    """설정 내용을 agent_config.json 파일에 저장합니다."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

def load_agencies():
    """기관 목록 파일(agencies.json)을 읽어옵니다."""
    if os.path.exists(AGENCIES_FILE):
        with open(AGENCIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # 기본 기관 목록 생성
        default_agencies = [
            {"name": "정보통신산업진흥원 (NIPA)", "url": "https://www.nipa.kr/kr/2/business/businessList.it", "domain": "과학기술", "type": "중앙정부", "scraper": "scrape_nipa"},
            {"name": "한국데이터산업진흥원 (K-DATA)", "url": "https://www.kdata.or.kr/kr/board/notice/boardList.do", "domain": "과학기술", "type": "중앙정부", "scraper": "scrape_kdata"},
        ]
        with open(AGENCIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_agencies, f, indent=4)
        return default_agencies

def save_agencies(agencies):
    """기관 목록을 agencies.json 파일에 저장합니다."""
    with open(AGENCIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(agencies, f, indent=4)

# --- 데이터 수집 에이전트 (Session 객체 사용으로 안정성 강화) ---
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
})
SESSION.verify = False # 모든 요청에 대해 SSL 인증서 검증 비활성화

def get_detail_from_page(detail_url, selector):
    """공고 상세 페이지에 접속하여 내용을 요약합니다. (범용 함수)"""
    try:
        response = SESSION.get(detail_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        content_div = soup.select_one(selector)
        if content_div:
            full_text = content_div.get_text(separator='\n', strip=True)
            return full_text[:150] + "..." if len(full_text) > 150 else full_text
        return "상세 내용을 찾을 수 없습니다."
    except Exception as e:
        return f"상세 내용 분석 중 오류 발생: {e}"

def scrape_nipa(agency):
    """정보통신산업진흥원(NIPA) 웹사이트에서 최신 공고를 스크래핑합니다."""
    try:
        response = SESSION.get(agency['url'])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        announcements = []
        for post in soup.select("div.board_box > ul > li"):
            flag_tag = post.select_one("span.flag")
            if flag_tag and "접수마감" in flag_tag.text:
                continue
            title_tag = post.select_one("div.subject > a")
            if title_tag:
                title = title_tag.text.strip()
                link = urljoin(agency['url'], title_tag['href'])
                summary = get_detail_from_page(link, ".view_con")
                date_tag = post.select_one("div.info > span.date")
                posted_date = date_tag.text.strip() if date_tag else ""
                announcements.append({"title": title, "link": link, "summary": summary, "posted_date": posted_date})
        return announcements
    except Exception as e:
        print(f"Error scraping {agency['name']}: {e}")
        return []

def scrape_kdata(agency):
    """한국데이터산업진흥원(K-DATA) 웹사이트에서 최신 공고를 스크래핑합니다."""
    try:
        response = SESSION.get(agency['url'])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        announcements = []
        for post in soup.select("div.board_list tbody > tr"):
            if post.select_one("td.td_notice"):
                continue
            title_tag = post.select_one("td.alignL a")
            if title_tag:
                title = title_tag.text.strip()
                link = urljoin(agency['url'], title_tag['href'])
                summary = "상세 내용은 링크를 참조하세요."
                date_tag = post.select_one("td:nth-of-type(4)")
                posted_date = date_tag.text.strip() if date_tag else ""
                announcements.append({"title": title, "link": link, "summary": summary, "posted_date": posted_date})
        return announcements
    except Exception as e:
        print(f"Error scraping {agency['name']}: {e}")
        return []

def scrape_iitp(agency):
    """정보통신기획평가원(IITP) 웹사이트에서 최신 공고를 스크래핑합니다."""
    try:
        response = SESSION.get(agency['url'])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        announcements = []
        for post in soup.select("div.board_box > ul > li"):
            flag_tag = post.select_one("span.flag")
            if flag_tag and "접수마감" in flag_tag.text:
                continue
            title_tag = post.select_one("div.subject > a")
            if title_tag:
                title = title_tag.text.strip()
                link = urljoin(agency['url'], title_tag['href'])
                summary = get_detail_from_page(link, ".view_con")
                date_tag = post.select_one("div.info > span.date")
                posted_date = date_tag.text.strip() if date_tag else ""
                announcements.append({"title": title, "link": link, "summary": summary, "posted_date": posted_date})
        return announcements
    except Exception as e:
        print(f"Error scraping {agency['name']}: {e}")
        return []

def scrape_aica(agency):
    """인공지능산업융합사업단(AICA) 웹사이트에서 최신 공고를 스크래핑합니다."""
    try:
        response = SESSION.get(agency['url'])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        announcements = []
        for post in soup.select("#gall_ul > li"):
            title_tag = post.select_one(".gall_subject a")
            if title_tag:
                title = title_tag.text.strip()
                link = urljoin(agency['url'], title_tag['href'])
                announcements.append({"title": title, "link": link, "summary": post.select_one(".gall_text").text.strip(), "posted_date": post.select_one(".gall_date").text.strip()})
        return announcements
    except Exception as e:
        print(f"Error scraping {agency['name']}: {e}")
        return []

def scrape_seoul_ai(agency):
    """서울 AI 허브 웹사이트에서 최신 공고를 스크래핑합니다."""
    try:
        response = SESSION.get(agency['url'])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        announcements = []
        for post in soup.select(".notice_list > ul > li"):
            title_tag = post.select_one(".notice_title a")
            if title_tag:
                title = title_tag.text.strip()
                link = urljoin(agency['url'], title_tag['href'])
                announcements.append({"title": title, "link": link, "summary": "상세 내용은 링크 참조", "posted_date": post.select_one(".notice_date").text.strip()})
        return announcements
    except Exception as e:
        print(f"Error scraping {agency['name']}: {e}")
        return []

def generate_summary_report(agency_name, announcements, template):
    """AI를 사용하여 기관별 공고 목록을 요약 리포트로 생성합니다."""
    try:
        from llm_config import gemini_pro_model
        _mname = gemini_pro_model()
    except Exception:
        _mname = "gemini-pro-latest"
    llm = ChatGoogleGenerativeAI(model=_mname, temperature=0.3, google_api_key=GEMINI_API_KEY)
    
    prompt = PromptTemplate.from_template(template)
    
    chain = prompt | llm | StrOutputParser()
    
    formatted_announcements = ""
    for ann in announcements:
        formatted_announcements += f"- 제목: {ann['title']}\n  요약: {ann.get('summary', '요약 정보 없음')}\n\n"
        
    report = chain.invoke({
        "agency_name": agency_name,
        "formatted_announcements": formatted_announcements
    })
    return report

# --- 스크래퍼 함수 딕셔너리 ---
SCRAPER_FUNCTIONS = {
    "scrape_nipa": scrape_nipa,
    "scrape_kdata": scrape_kdata,
    "scrape_iitp": scrape_iitp,
    "scrape_aica": scrape_aica,
    "scrape_seoul_ai": scrape_seoul_ai,
}

def run_monitoring(target_agencies, keywords=[]):
    """지정된 기관 목록과 키워드를 바탕으로 모니터링을 실행하고 실시간 상태를 보고합니다."""
    all_results = {}
    total_agencies = len(target_agencies)
    yield {"type": "log", "status": "info", "message": f"총 {total_agencies}개 기관에 대한 모니터링을 시작합니다."}

    for i, agency in enumerate(target_agencies):
        yield {"type": "progress", "value": (i) / total_agencies, "text": f"({i+1}/{total_agencies}) {agency['name']} 처리 중..."}
        
        scraper_function_name = agency.get("scraper")
        if not scraper_function_name:
            yield {"type": "log", "status": "warning", "message": f"-> {agency['name']}: 스크래퍼가 지정되지 않아 건너뜁니다."}
            continue

        scraper_function = SCRAPER_FUNCTIONS.get(scraper_function_name)
        if not scraper_function:
            yield {"type": "log", "status": "error", "message": f"-> {agency['name']}: 스크래퍼 함수 '{scraper_function_name}'를 찾을 수 없습니다."}
            continue

        yield {"type": "log", "status": "info", "message": f"-> {agency['name']} 사이트 접속 및 데이터 수집 중..."}
        
        try:
            announcements = scraper_function(agency)
            yield {"type": "log", "status": "success", "message": f"-> {agency['name']}: {len(announcements)}개 공고를 성공적으로 수집했습니다."}
            
            if announcements and keywords:
                yield {"type": "log", "status": "info", "message": f"-> 키워드 필터링 중: {keywords}"}
                original_count = len(announcements)
                filtered_announcements = [
                    ann for ann in announcements 
                    if any(k.lower() in (ann['title'] + ann.get('summary', '')).lower() for k in keywords)
                ]
                announcements = filtered_announcements
                yield {"type": "log", "status": "success", "message": f"-> {original_count}개 중 {len(announcements)}개 공고가 키워드와 일치합니다."}
            
            if announcements:
                all_results[agency['name']] = announcements
        except Exception as e:
            yield {"type": "log", "status": "error", "message": f"-> {agency['name']} 처리 중 오류 발생: {e}"}

    yield {"type": "progress", "value": 1.0, "text": "모니터링 완료!"}
    yield {"type": "result", "data": all_results}

def send_summary_email(results, recipients):
    """수집된 공고 요약 정보를 지정된 이메일로 발송합니다."""
    if not any(results.values()):
        print("발송할 신규 공고가 없어 이메일을 보내지 않습니다.")
        return

    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    if not SMTP_USER or not SMTP_PASSWORD:
        print("SMTP 사용자 정보가 설정되지 않아 이메일을 발송할 수 없습니다.")
        return

    today_str = datetime.now().strftime("%Y년 %m월 %d일")
    subject = f"[{today_str}] 신규 국책사업 공고 알림"
    body = f"<h2>{today_str} 신규 국책사업 목록입니다.</h2>"

    for agency, announcements in results.items():
        if not announcements: continue
        body += f"<h3>- {agency} ({len(announcements)}건)</h3><ul>"
        for ann in announcements:
            body += f"<li><a href='{ann['link']}'><strong>{ann['title']}</strong></a><br>{ann.get('summary', '요약 정보 없음')}</li>"
        body += "</ul><hr>"

    msg = MIMEText(body, 'html')
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = ", ".join(recipients)

    try:
        with smtplib.SMTP(os.getenv("SMTP_SERVER", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", 587))) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
        print(f"{', '.join(recipients)}에게 이메일 발송 성공!")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

if __name__ == "__main__":
    print("===== 국책사업 모니터링 에이전트 시작 =====")
    config = load_config()
    recipients = config.get("recipients", [])
    keywords = config.get("crawling_keywords", [])
    
    agencies = load_agencies()
    
    final_results = {}
    for update in run_monitoring(agencies, keywords):
        if update['type'] == 'log':
            print(update['message'])
        elif update['type'] == 'result':
            final_results = update['data']
            
    if final_results:
        send_summary_email(final_results, recipients)
    print("===== 에이전트 작업 완료 =====")