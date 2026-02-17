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
        color: rgb(49, 51, 63);
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
    
    /* [중요] 인쇄 모드 스타일 */
    @media print {
        header, footer, aside, 
        [data-testid="stSidebar"], [data-testid="stToolbar"], 
        .stButton, .stDownloadButton, .stExpander, .stForm, 
        div[data-testid="stVerticalBlockBorderWrapper"], button,
        .no-print, 
        .sort-area, .stSelectbox, .stCheckbox,
        div[data-testid="stPopover"]
        { display: none !important; }

        body, .stApp { 
            background-color: white !important; 
            -webkit-print-color-adjust: exact !important;
            zoom: 75%; 
        }
        * { color: black !important; text-shadow: none !important; }

        .main .block-container { max-width: 100% !important; width: 100% !important; padding: 0 !important; margin: 0 !important; }
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] { height: auto !important; width: 100% !important; overflow: visible !important; display: block !important; }

        div[data-testid="stDataEditor"], .stPlotlyChart { break-inside: avoid !important; margin-bottom: 20px !important; width: 100% !important; }
        div[data-testid="stDataEditor"] table { font-size: 11px !important; border: 1px solid #000 !important; width: 100% !important; }

        @page { size: portrait; margin: 1cm; }
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# 메인 타이틀
st.markdown('<div class="title-text">📅 디자인1본부 1팀 일정</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. 데이터 로드 및 세션 상태 관리 (속도 최적화의 핵심)
# -----------------------------------------------------------------------------
# 세션 상태 초기화
if 'show_completed' not in st.session_state:
    st.session_state['show_completed'] = False

# 구글 시트에서 데이터를 불러와서 전처리하는 함수
def fetch_data_from_sheets():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="Sheet1", ttl=0) # ttl=0: 즉시 갱신
    return df

# [최적화] 세션 스테이트에 데이터가 없으면 로드, 있으면 기존 데이터 사용
if 'data' not in st.session_state:
    try:
        with st.spinner("데이터를 불러오는 중..."):
            raw_data = fetch_data_from_sheets()
            
            # 전처리 과정 (여기서 한 번만 수행)
            required_cols = ["프로젝트명", "구분", "담당자", "Activity", "시작일", "종료일", "진행률"]
            if raw_data.empty:
                for col in required_cols:
                    raw_data[col] = ""
                raw_data["진행률"] = 0
            
            raw_data["시작일"] = pd.to_datetime(raw_data["시작일"], errors='coerce')
            raw_data["종료일"] = pd.to_datetime(raw_data["종료일"], errors='coerce')
            
            if "진행률" in raw_data.columns and raw_data["진행률"].dtype == 'object':
                raw_data["진행률"] = raw_data["진행률"].astype(str).str.replace('%', '')
            raw_data["진행률"] = pd.to_numeric(raw_data["진행률"], errors='coerce').fillna(0).astype(int)
            
            # 고유 ID 생성 (인덱스 보존)
            raw_data["_original_id"] = raw_data.index
            
            # 세션에 저장
            st.session_state['data'] = raw_data
            
    except Exception as e:
        st.error(f"⚠️ 데이터 연결 실패. 인터넷 상태를 확인하세요.\n에러: {e}")
        st.stop()

# 이제부터는 st.session_state['data']를 사용하여 작업 (매우 빠름)
data = st.session_state['data'].copy()

# 남은기간 계산 (매번 갱신)
today = pd.to_datetime(datetime.today().strftime("%Y-%m-%d"))
data["남은기간"] = (data["종료일"] - today).dt.days.fillna(0).astype(int)
data["진행상황"] = data["진행률"]

# 리스트 추출 함수
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
if st.session_state['show_completed']:
    chart_base_data = data.copy()
else:
    chart_base_data = data[data["진행률"] < 100].copy()

chart_data = chart_base_data.dropna(subset=["시작일", "종료일"]).copy()

if not chart_data.empty:
    chart_data["프로젝트명_줄바꿈"] = chart_data["프로젝트명"].apply(lambda x: wrap_labels(x))
    
    custom_colors = px.colors.qualitative.Pastel 

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
    
    # 바 끝에 담당자 이름 표시
    fig.add_trace(go.Scatter(
        x=chart_data["종료일"], 
        y=chart_data["프로젝트명_줄바꿈"],
        text="  " + chart_data["담당자"].astype(str), 
        mode="text",
        textposition="middle right", 
        textfont=dict(size=8),
        showlegend=False
    ))
    
    # 날짜 라벨
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
        curr += timedelta(days=1)

    view_start = today - timedelta(days=3)
    view_end = today + timedelta(days=11)

    fig.update_layout(
        title=dict(
            text='<b>Project Schedule</b>',
            font=dict(size=15),
            x=0, y=1, xanchor='left', yanchor='top'
        ),
        xaxis_title="", yaxis_title="", 
        barmode='group', bargap=0.2, 
        height=500, 
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=50, t=30, b=10),
        dragmode="pan", 
        legend=dict(
            orientation="v", 
            yanchor="bottom", y=0, 
            xanchor="left", x=1.01
        ),
        xaxis=dict(range=[view_start, view_end])
    )
    
    fig.update_xaxes(
        side="top", tickmode="array", tickvals=tick_vals, ticktext=tick_text,
        tickfont=dict(size=10),
        showgrid=True, 
        gridcolor='rgba(128, 128, 128, 0.2)', 
        griddash='dot'
    )
    
    fig.update_yaxes(
        fixedrange=True, autorange="reversed", showticklabels=True,
        tickfont=dict(size=12),
        showgrid=False, # 구분선 삭제
        gridwidth=1,
        layer="below traces"
    )

    fixed_holidays = ["2024-01-01", "2024-02-09", "2024-02-10", "2024-02-11", "2024-02-12", "2024-03-01", "2024-04-10", "2024-05-05", "2024-05-06", "2024-05-15", "2024-06-06", "2024-08-15", "2024-09-16", "2024-09-17", "2024-09-18", "2024-10-03", "2024-10-09", "2024-12-25", "2025-01-01", "2025-01-28", "2025-01-29", "2025-01-30", "2025-03-01", "2025-05-05", "2025-05-06", "2025-06-06", "2025-08-15", "2025-10-03", "2025-10-05", "2025-10-06", "2025-10-07", "2025-10-09", "2025-12-25"]

    if pd.notnull(label_start) and pd.notnull(label_end):
        c_date = label_start
        while c_date <= label_end:
            is_weekend = c_date.weekday() in [5, 6]
            is_holiday = c_date.strftime("%Y-%m-%d") in fixed_holidays
            if is_weekend or is_holiday:
                fig.add_vrect(x0=c_date, x1=c_date + timedelta(days=1), fillcolor="rgba(128, 128, 128, 0.1)", layer="below", line_width=0)
            if c_date.weekday() == 0:
                fig.add_vline(x=c_date.timestamp() * 1000, line_width=2, line_dash="solid", line_color="rgba(128, 128, 128, 0.3)")
            c_date += timedelta(days=1)
            
    # 오늘 날짜 (빨간 파선)
    fig.add_vline(
        x=datetime.today().timestamp() * 1000, 
        line_width=8, 
        line_dash="dash", 
        line_color="rgba(255, 0, 0, 0.6)"
    )

    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': True})
else:
    st.info("표시할 일정이 없습니다.")

# -----------------------------------------------------------------------------
# 5. [입력 섹션] (차트 밑으로 이동)
# -----------------------------------------------------------------------------
st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

with st.expander("➕ 새 일정 등록하기"):
    with st.form("add_task_form"):
        c1, c2, c3 = st.columns(3)
        def input_or_select(label, options, key):
            extended_options = options + ["➕ 직접 입력"]
            selected = st.selectbox(label, extended_options, key=f"{key}_sel")
            if selected == "➕ 직접 입력":
                return st.text_input(f"└ {label} 입력", key=f"{key}_txt")
            return selected

        with c1:
            final_name = input_or_selec
