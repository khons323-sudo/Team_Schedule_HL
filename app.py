import streamlit as st
import pandas as pd
import plotly.express as px
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
    /* 1. 메인 타이틀 & 서브헤더 스타일 (크기 통일) */
    .title-text, .subheader-text {
        font-size: 1.3rem !important; /* 업무현황 크기와 동일하게 맞춤 */
        font-weight: 700;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.5;
        color: rgb(49, 51, 63);
    }
    
    /* 상단 여백 최소화 */
    /.block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
    }/

    /* 입력 폼 스타일링 */
    div[data-testid="stForm"] .stSelectbox { margin-bottom: -15px !important; }
    div[data-testid="stForm"] .stTextInput { margin-top: 0px !important; }
    
    /* 2. 정렬 컨트롤 스타일 (글자 크기 통일 및 수직 정렬) */
    .sort-label {
        font-size: 14px; /* 스트림릿 위젯 기본 폰트사이즈와 통일 */
        font-weight: 600;
        display: flex;
        align-items: center;
        justify-content: flex-end; /* 우측 정렬 */
        height: 40px; /* 셀렉트박스 높이와 유사하게 */
        padding-right: 10px;
    }
    
    /* 선택박스, 토글 등 위젯 수직 정렬 보정 */
    div[data-testid="stSelectbox"] {
        margin-top: 2px;
    }
    div[data-testid="stCheckbox"] {
        margin-top: 8px; /* 토글 버튼 위치 미세 조정 */
    }
    div[data-testid="stCheckbox"] label {
        font-size: 14px !important;
    }

    /* [중요] 인쇄 모드 스타일 (세로 방향, 한 페이지 맞춤) */
    @media print {
        /* 1. 숨길 요소들 (버튼, 사이드바, 입력폼 등) */
        header, footer, aside, 
        [data-testid="stSidebar"], [data-testid="stToolbar"], 
        .stButton, .stDownloadButton, .stExpander, .stForm, 
        div[data-testid="stVerticalBlockBorderWrapper"], button,
        .no-print
        { 
            display: none !important; 
        }

        /* 2. 배경 및 글자색 강제 설정 (흰 종이에 검은 글씨) */
        body, .stApp { 
            background-color: white !important; 
            -webkit-print-color-adjust: exact !important;
            zoom: 75%; /* [핵심] 세로 용지에 맞게 전체 축소 */
        }
        * { 
            color: black !important; 
            text-shadow: none !important; 
        }

        /* 3. 메인 콘텐츠 확장 */
        .main .block-container { 
            max-width: 100% !important; 
            width: 100% !important; 
            padding: 0 !important; 
            margin: 0 !important; 
        }
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] { 
            height: auto !important; 
            overflow: visible !important; 
            display: block !important; 
        }

        /* 4. 차트 및 표 설정 */
        div[data-testid="stDataEditor"], .stPlotlyChart { 
            break-inside: avoid !important; 
            margin-bottom: 20px !important; 
        }
        div[data-testid="stDataEditor"] table { 
            font-size: 11px !important; 
            border: 1px solid #000 !important; 
        }

        /* 5. 페이지 설정 (세로 방향) */
        @page { 
            size: portrait; 
            margin: 1cm; 
        }
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

st.title("HL 디자인1본부 1팀 작업일정")

# -----------------------------------------------------------------------------
# [수정] 메인 타이틀 복구 (업무현황 크기와 동일)
# -----------------------------------------------------------------------------
st.markdown('<div class="title-text">📅 디자인1본부 1팀 일정</div>', unsafe_allow_html=True)

# 세션 상태 초기화
if 'show_completed' not in st.session_state:
    st.session_state.show_completed = False

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
# 4. [입력 섹션]
# -----------------------------------------------------------------------------
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
            final_name = input_or_select("1. 프로젝트명", projects_list, "proj")
            final_item = input_or_select("2. 구분", items_list, "item")
        with c2:
            final_member = input_or_select("3. 담당자", members_list, "memb")
            final_act = input_or_select("4. Activity", activity_list, "act")
        with c3:
            p_start = st.date_input("5. 시작일", datetime.today())
            p_end = st.date_input("6. 종료일", datetime.today())
            st.markdown("<br>", unsafe_allow_html=True)
            submit_btn = st.form_submit_button("일정 추가", use_container_width=True)
        
        if submit_btn:
            if not final_name:
                st.error("프로젝트명을 입력해주세요.")
            else:
                new_row = pd.DataFrame([{
                    "프로젝트명": final_name, "구분": final_item, "담당자": final_member,
                    "Activity": final_act, "시작일": p_start.strftime("%Y-%m-%d"),
                    "종료일": p_end.strftime("%Y-%m-%d"), "진행률": 0
                }])
                save_data = data[required_cols].copy()
                save_data["시작일"] = save_data["시작일"].dt.strftime("%Y-%m-%d")
                save_data["종료일"] = save_data["종료일"].dt.strftime("%Y-%m-%d")
                final_df = pd.concat([save_data, new_row], ignore_index=True)
                
                conn = st.connection("gsheets", type=GSheetsConnection)
                conn.update(worksheet="Sheet1", data=final_df)
                load_data.clear()
                st.rerun()

# -----------------------------------------------------------------------------
# 5. [시각화 섹션] 간트차트
# -----------------------------------------------------------------------------
# 필터링
if st.session_state.show_completed:
    base_data = data.copy()
else:
    base_data = data[data["진행률"] < 100].copy()

chart_data = base_data.dropna(subset=["시작일", "종료일"]).copy()

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
        curr += timedelta(days=1)

    # 초기 화면 2주
    view_start = today - timedelta(days=3)
    view_end = today + timedelta(days=11)

    fig.update_layout(
        xaxis_title="", yaxis_title="", 
        barmode='group', bargap=0.2, 
        height=300, 
        paper_bgcolor='rgb(40, 40, 40)', plot_bgcolor='rgb(40, 40, 40)',
        font=dict(color="white"),
        margin=dict(l=10, r=10, t=20, b=10),
        dragmode="pan", 
        legend=dict(orientation="v", yanchor="bottom", y=0, xanchor="left", x=1.01),
        xaxis=dict(range=[view_start, view_end])
    )
    
    fig.update_xaxes(
        side="top", tickmode="array", tickvals=tick_vals, ticktext=tick_text,
        tickfont=dict(color="white", size=10),
        showgrid=True, gridcolor='rgba(255, 255, 255, 0.1)', griddash='dot'
    )
    
    fig.update_yaxes(
        fixedrange=True, autorange="reversed", showticklabels=True,
        tickfont=dict(color="white", size=12),
        showgrid=True, gridcolor='rgba(200, 200, 200, 0.3)', gridwidth=1,
        layer="below traces"
    )

    # 공휴일(고정)
    fixed_holidays = ["2024-01-01", "2024-02-09", "2024-02-10", "2024-02-11", "2024-02-12", "2024-03-01", "2024-04-10", "2024-05-05", "2024-05-06", "2024-05-15", "2024-06-06", "2024-08-15", "2024-09-16", "2024-09-17", "2024-09-18", "2024-10-03", "2024-10-09", "2024-12-25", "2025-01-01", "2025-01-28", "2025-01-29", "2025-01-30", "2025-03-01", "2025-05-05", "2025-05-06", "2025-06-06", "2025-08-15", "2025-10-03", "2025-10-05", "2025-10-06", "2025-10-07", "2025-10-09", "2025-12-25"]

    if pd.notnull(label_start) and pd.notnull(label_end):
        c_date = label_start
        while c_date <= label_end:
            is_weekend = c_date.weekday() in [5, 6]
            is_holiday = c_date.strftime("%Y-%m-%d") in fixed_holidays
            if is_weekend or is_holiday:
                fig.add_vrect(x0=c_date, x1=c_date + timedelta(days=1), fillcolor="rgba(100, 100, 100, 0.3)", layer="below", line_width=0)
            if c_date.weekday() == 0:
                fig.add_vline(x=c_date.timestamp() * 1000, line_width=2, line_dash="solid", line_color="rgba(200, 200, 200, 0.6)")
            c_date += timedelta(days=1)

    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': True})
else:
    st.info("표시할 일정이 없습니다.")

# -----------------------------------------------------------------------------
# 6. [간격 조정 및 컨트롤 섹션]
# -----------------------------------------------------------------------------
st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

# [수정] 업무현황, 정렬 컨트롤 배치 (아이콘, 콜론 삭제 및 정렬 맞춤)
c_title, c_sort_label, c_sort_box, c_sort_toggle = st.columns([0.25, 0.1, 0.3, 0.35])

with c_title:
    # 업무현황 타이틀
    st.markdown('<div class="subheader-text no-print">📝 업무 현황</div>', unsafe_allow_html=True)

with c_sort_label:
    # 정렬기준 라벨 (아이콘 제거, 콜론 제거, 우측 정렬)
    st.markdown('<div class="sort-label no-print">정렬 기준</div>', unsafe_allow_html=True)

with c_sort_box:
    # 정렬 기준 선택
    sort_col = st.selectbox("정렬", ["프로젝트명", "구분", "담당자", "시작일", "종료일", "진행률"], label_visibility="collapsed")

with c_sort_toggle:
    # 오름차순 토글
    sort_asc = st.toggle("오름차순 정렬", value=True)

# 정렬 적용
filtered_df = base_data.copy()
filtered_df = filtered_df.sort_values(by=sort_col, ascending=sort_asc)

# -----------------------------------------------------------------------------
# 7. 버튼 그룹 (인쇄 버튼 삭제)
# -----------------------------------------------------------------------------
# [수정] 인쇄 버튼 삭제, 나머지 버튼 2개 등분 배치
b1, b2, b3 = st.columns([0.3, 0.3, 0.4]) # 비율 조정
with b1:
    download_cols = required_cols + ["남은기간"]
    final_down_cols = [c for c in download_cols if c in data.columns]
    csv = data[final_down_cols].to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 엑셀(CSV) 다운로드", data=csv, file_name='design_schedule.csv', mime='text/csv', use_container_width=True)
with b2:
    btn_text = "🙈 완료된 업무 끄기" if st.session_state.show_completed else "👁️ 완료된 업무 보기"
    if st.button(btn_text, use_container_width=True):
        st.session_state.show_completed = not st.session_state.show_completed
        st.rerun()
# with b3: 인쇄 버튼 삭제됨

# -----------------------------------------------------------------------------
# 8. 데이터 에디터
# -----------------------------------------------------------------------------
st.markdown('<div class="no-print" style="color:gray; font-size:0.8rem; margin-bottom:5px;">※ 내용을 수정한 후 <b>저장</b> 버튼을 꼭 누르세요. (브라우저 인쇄 단축키: Ctrl+P)</div>', unsafe_allow_html=True)

display_cols = ["프로젝트명", "구분", "담당자", "Activity", "시작일", "종료일", "남은기간", "진행률", "진행상황"]
final_display_cols = [c for c in display_cols if c in filtered_df.columns]

dynamic_height = (len(filtered_df) + 1) * 35 + 3

edited_df = st.data_editor(
    filtered_df,
    height=dynamic_height,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "프로젝트명": st.column_config.SelectboxColumn("프로젝트명", options=projects_list, required=True),
        "구분": st.column_config.SelectboxColumn("구분", options=items_list),
        "담당자": st.column_config.SelectboxColumn("담당자", options=members_list),
        "Activity": st.column_config.SelectboxColumn("Activity", options=activity_list),
        "진행률": st.column_config.NumberColumn("진행률", min_value=0, max_value=100, step=5, format="%d"),
        "진행상황": st.column_config.ProgressColumn("진행상황(Bar)", format="%d%%", min_value=0, max_value=100),
        "시작일": st.column_config.DateColumn("시작일", format="YYYY-MM-DD"),
        "종료일": st.column_config.DateColumn("종료일", format="YYYY-MM-DD"),
        "남은기간": st.column_config.NumberColumn("남은기간(일)", format="%d일", disabled=True),
    },
    column_order=final_display_cols,
    hide_index=True,
    key="data_editor"
)

# -----------------------------------------------------------------------------
# 9. 저장 버튼
# -----------------------------------------------------------------------------
if st.button("💾 변경사항 저장하기", type="primary"):
    try:
        save_part_df = edited_df[required_cols + ["_original_id"]]
        visible_ids = edited_df["_original_id"].dropna().tolist()
        hidden_data = data[~data["_original_id"].isin(visible_ids)].copy()
        
        save_part_df = save_part_df[required_cols]
        hidden_part_df = hidden_data[required_cols]
        
        final_save_df = pd.concat([save_part_df, hidden_part_df], ignore_index=True)
        
        final_save_df["시작일"] = pd.to_datetime(final_save_df["시작일"]).dt.strftime("%Y-%m-%d").fillna("")
        final_save_df["종료일"] = pd.to_datetime(final_save_df["종료일"]).dt.strftime("%Y-%m-%d").fillna("")
        final_save_df["진행률"] = pd.to_numeric(final_save_df["진행률"]).fillna(0).astype(int)

        conn.update(worksheet="Sheet1", data=final_save_df)
        load_data.clear()
        
        st.toast("저장되었습니다! (잠시 후 새로고침)", icon="✅")
        time.sleep(1)
        st.rerun()
        
    except Exception as e:
        st.error(f"저장 중 오류 발생: {e}")
