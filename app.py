import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import time
import textwrap 

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 디자인 CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="디자인1본부 일정관리", layout="wide")

# CSS: 화면 및 인쇄 스타일링
custom_css = """
<style>
    /* 1. 메인 타이틀 & 서브헤더 스타일 */
    .title-text, .subheader-text {
        font-size: 1.3rem !important;
        font-weight: 700;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.5;
    }
    
    /* 상단 여백 최소화 */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
    }

    /* 입력 폼 스타일링 */
    div[data-testid="stForm"] .stSelectbox { margin-bottom: -15px !important; }
    div[data-testid="stForm"] .stTextInput { margin-top: 0px !important; }
    
    /* 정렬 컨트롤 라벨 스타일 */
    .sort-label {
        font-size: 14px;
        font-weight: 600;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        height: 40px;
        padding-right: 10px;
    }
    
    div[data-testid="stSelectbox"] { margin-top: 2px; }
    div[data-testid="stCheckbox"] { margin-top: 8px; }
    div[data-testid="stCheckbox"] label { font-size: 14px !important; }
    
    /* 팝오버 버튼(➕) 스타일 */
    div[data-testid="stPopover"] button {
        margin-top: 8px; /* 다른 버튼들과 높이 맞춤 */
        font-weight: bold;
    }

    /* [중요] 인쇄 모드 스타일 */
    @media print {
        /* 숨길 요소들 */
        header, footer, aside, 
        [data-testid="stSidebar"], [data-testid="stToolbar"], 
        .stButton, .stDownloadButton, .stExpander, .stForm, 
        div[data-testid="stVerticalBlockBorderWrapper"], button,
        .no-print, 
        .sort-area, .stSelectbox, .stCheckbox,
        div[data-testid="stPopover"]
        { 
            display: none !important; 
        }

        /* 배경 및 글자색 강제 설정 (인쇄 시 가독성 확보) */
        body, .stApp { 
            background-color: white !important; 
            -webkit-print-color-adjust: exact !important;
            zoom: 75%; 
        }
        * { 
            color: black !important; 
            text-shadow: none !important; 
        }

        .main .block-container { 
            max-width: 100% !important; 
            width: 100% !important; 
            padding: 0 !important; 
            margin: 0 !important; 
        }
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] { 
            height: auto !important; 
            width: 100% !important;
            overflow: visible !important; 
            display: block !important; 
        }

        div[data-testid="stDataEditor"], .stPlotlyChart { 
            break-inside: avoid !important; 
            margin-bottom: 20px !important; 
            width: 100% !important; 
        }
        div[data-testid="stDataEditor"] table { 
            font-size: 11px !important; 
            border: 1px solid #000 !important; 
            width: 100% !important;
        }

        @page { 
            size: portrait; 
            margin: 1cm; 
        }
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# 메인 타이틀
st.markdown('<div class="title-text">📅 디자인1본부 1팀 일정</div>', unsafe_allow_html=True)

# 세션 상태 초기화
if 'show_completed' not in st.session_state:
    st.session_state['show_completed'] = False

# -----------------------------------------------------------------------------
# 2. 데이터 로드 및 캐싱
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="Sheet1")
    return df

try:
    data = load_data()
except Exception as e:
    st.error(f"⚠️ 데이터 연결 실패. 인터넷 상태를 확인하세요.\n에러: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. 데이터 전처리
# -----------------------------------------------------------------------------
required_cols = ["프로젝트명", "구분", "담당자", "Activity", "시작일", "종료일", "진행률"]

if data.empty:
    for col in required_cols:
        data[col] = ""
    data["진행률"] = 0

data["시작일"] = pd.to_datetime(data["시작일"], errors='coerce')
data["종료일"] = pd.to_datetime(data["종료일"], errors='coerce')
today = pd.to_datetime(datetime.today().strftime("%Y-%m-%d"))
data["남은기간"] = (data["종료일"] - today).dt.days.fillna(0).astype(int)

if "진행률" in data.columns and data["진행률"].dtype == 'object':
    data["진행률"] = data["진행률"].astype(str).str.replace('%', '')
data["진행률"] = pd.to_numeric(data["진행률"], errors='coerce').fillna(0).astype(int)

data["진행상황"] = data["진행률"]
data["_original_id"] = data.index

# 리스트 추출
def get_unique_list(df, col_name):
    if col_name in df.columns:
        return sorted(df[col_name].astype(str).dropna().unique().tolist())
    return []

projects_list = get_unique_list(data, "프로젝트명")
items_list = get_unique_list(data, "구분")
members_list = get_unique_list(data, "담당자")
activity_list = get_unique_list(data, "Activity")

def wrap_labels(text, width=10):
    if pd.isna(text): return ""
    return "<br>".join(textwrap.wrap(str(text), width=width, break_long_words=True))

# -----------------------------------------------------------------------------
# 4. [시각화 섹션] 간트차트
# -----------------------------------------------------------------------------
# 필터링 (토글 상태에 따라)
if st.session_state['show_completed']:
    base_data = data.copy()
else:
    base_data = data[data["진행률"] < 100].copy()

chart_data = base_data.dropna(subset=["시작일", "종료일"]).copy()

if not chart_data.empty:
    chart_data["프로젝트명_줄바꿈"] = chart_data["프로젝트명"].apply(lambda x: wrap_labels(x))
    # 담당자 이름 앞에 공백 추가 (바와 겹치지 않게 띄우기용)
    chart_data["담당자_라벨"] = "  " + chart_data["담당자"].astype(str)
    
    custom_colors = px.colors.qualitative.Pastel 

    # 1. 기본 바 차트
    fig = px.timeline(
        chart_data, 
        x_start="시작일", x_end="종료일", 
        y="프로젝트명_줄바꿈",
        color="담당자",
        color_discrete_sequence=custom_colors,
        hover_name="프로젝트명",
        hover_data=["구분", "Activity", "진행률", "남은기간"],
        title=""
    )
    
    # 2. 바 끝에 담당자 이름 표시
    fig.add_trace(go.Scatter(
        x=chart_data["종료일"], # X축 위치: 바의 끝
        y=chart_data["프로젝트명_줄바꿈"], # Y축 위치: 바와 동일 (수직 일치)
        text=chart_data["담당자_라벨"], 
        mode="text",
        textposition="middle right", # 바의 끝선 기준 우측 배치
        # [수정] 글자 크기 8, 시스템 테마 따름 (색상 지정 안함)
        textfont=dict(size=8), 
        showlegend=False
    ))
    
    # 날짜 라벨 (Wide Range)
    min_dt = chart_data["시작일"].min()
    max_dt = chart_data["종료일"].max()
    if pd.isnull(min_dt): min_dt = today
    if pd.isnull(max_dt): max_dt = today
    
    label_start = min_dt - timedelta(days=90)
    label_end = max_dt + timedelta(days=90)
    
    tick_vals = []
    tick_text = []
    korean_days = ["월", "화", "수", "목", "금", "토", "일"]
    curr = label_start
    while curr <= label_end:
        tick_vals.append(curr)
        label = f"{curr.month}월<br>{curr.day}<br>({korean_days[curr.weekday()]})"
        tick_text.append(label)
