import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import time
import streamlit.components.v1 as components
import textwrap 

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 인쇄용 CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="디자인1본부 일정관리", layout="wide")

# 인쇄 시 적용될 CSS (버튼 숨김, 배경 흰색, 글자 검은색 강제)
print_css = """
<style>
/* 입력 폼 스타일링 */
div[data-testid="stForm"] .stSelectbox { margin-bottom: -15px !important; }
div[data-testid="stForm"] .stTextInput { margin-top: 0px !important; }

@media print {
    /* UI 숨기기 */
    header, footer, aside, 
    [data-testid="stSidebar"], [data-testid="stToolbar"], 
    .stButton, .stDownloadButton, .stExpander, .stForm, 
    div[data-testid="stVerticalBlockBorderWrapper"],
    button {
        display: none !important;
    }

    /* 잉크 절약 및 가독성 확보 */
    body, .stApp, .block-container, div[data-testid="stDataEditor"] {
        background-color: white !important;
        color: black !important;
    }
    
    div[data-testid="stDataEditor"] * {
        color: black !important;
        font-weight: 500 !important;
    }

    /* 레이아웃 확장 */
    .main .block-container {
        max-width: 100% !important;
        width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        overflow: visible !important;
        height: auto !important;
        visibility: visible !important;
    }

    /* 폰트 조정 */
    div[data-testid="stDataEditor"] table {
        font-size: 10px !important;
    }

    @page {
        size: landscape;
        margin: 1cm;
    }
}
</style>
"""
st.markdown(print_css, unsafe_allow_html=True)

st.title("📅 디자인1본부 1팀 작업일정")

# 세션 상태 초기화
if 'show_completed' not in st.session_state:
    st.session_state.show_completed = False

# -----------------------------------------------------------------------------
# 2. 구글 시트 연결
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    data = conn.read(worksheet="Sheet1", ttl=0)
except Exception as e:
    st.error(f"⚠️ 데이터 불러오기 실패. 구글 시트 탭 이름이 'Sheet1'인지 확인하세요.\n에러: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. 데이터 전처리
# -----------------------------------------------------------------------------
required_cols = ["프로젝트명", "구분", "담당자", "Activity", "시작일", "종료일", "진행률"]

if data.empty:
    for col in required_cols:
        data[col] = ""
    data["진행률"] = 0

# 날짜 변환
data["시작일"] = pd.to_datetime(data["시작일"], errors='coerce')
data["종료일"] = pd.to_datetime(data["종료일"], errors='coerce')

# 남은기간 계산
today = pd.to_datetime(datetime.today().strftime("%Y-%m-%d"))
data["남은기간"] = (data["종료일"] - today).dt.days.fillna(0).astype(int)

# 진행률 숫자 변환
if "진행률" in data.columns and data["진행률"].dtype == 'object':
    data["진행률"] = data["진행률"].astype(str).str.replace('%', '')
data["진행률"] = pd.to_numeric(data["진행률"], errors='coerce').fillna(0).astype(int)

# 시각화용 컬럼
data["진행상황"] = data["진행률"]
data["_original_id"] = data.index

# 리스트 추출 함수
def get_unique_list(col_name):
    if col_name in data.columns:
        return sorted(data[col_name].astype(str).dropna().unique().tolist())
    return []

projects_list = get_unique_list("프로젝트명")
items_list = get_unique_list("구분")
members_list = get_unique_list("담당자")
activity_list = get_unique_list("Activity")

# 프로젝트명 줄바꿈 함수
def wrap_labels(text, width=10):
    if pd.isna(text): return ""
    return "<br>".join(textwrap.wrap(str(text), width=width, break_long_words=True))

# -----------------------------------------------------------------------------
# 4. [입력 섹션] 새 일정 등록
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
                    "프로젝트명": final_name,
                    "구분": final_item,
                    "담당자": final_member,
                    "Activity": final_act,
                    "시작일": p_start.strftime("%Y-%m-%d"),
                    "종료일": p_end.strftime("%Y-%m-%d"),
                    "진행률": 0
                }])
                
                save_data = data[required_cols].copy()
                save_data["시작일"] = save_data["시작일"].dt.strftime("%Y-%m-%d")
                save_data["종료일"] = save_data["종료일"].dt.strftime("%Y-%m-%d")
                
                final_df = pd.concat([save_data, new_row], ignore_index=True)
                conn.update(worksheet="Sheet1", data=final_df)
                st.cache_data.clear()
                st.rerun()

# -----------------------------------------------------------------------------
# 5. [시각화 섹션] 간트차트
# -----------------------------------------------------------------------------
st.subheader("📊 일정")

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
    
    view_start = today - timedelta(days=3)
    view_end = today + timedelta(days=11)
    
    tick_vals = []
    tick_text = []
    korean_days = ["월", "화", "수", "목", "금", "토", "일"]
    
    curr = view_start
    while curr <= view_end:
        tick_vals.append(curr)
        label = f"{curr.month}월<br>{curr.day}<br>({korean_days[curr.weekday()]})"
        tick_text.append(label)
        curr += timedelta(days=1)

    fig.update_layout(
        xaxis_title="", 
        yaxis_title="", 
        barmode='group', 
        bargap=0.2, 
        height=500,
        paper_bgcolor='rgb(40, 40, 40)',
        plot_bgcolor='rgb(40, 40, 40)',
        font=dict(color="white"),
        margin=dict(l=10, r=10, t=60, b=10),
        dragmode="pan", 
        legend=dict(
            orientation="v",
            yanchor="bottom",
            y=0,
            xanchor="left",
            x=1.01
        ),
        xaxis=dict(range=[view_start, view_end])
    )
    
    fig.update_xaxes(
        side="top",
        tickmode="array", 
        tickvals=tick_vals,
        ticktext=tick_text,
        tickfont=dict(color="white", size=10),
        showgrid=True,
        gridcolor='rgba(255, 255, 255, 0.1)', 
        griddash='dot'
    )
    
    fig.update_yaxes(
        fixedrange=True,
        autorange="reversed",
        showticklabels=True,
        tickfont=dict(color="white", size=12),
        showgrid=True,
        gridcolor='rgba(200, 200, 200, 0.3)',
        gridwidth=1,
        layer="below traces"
    )

    grid_start = chart_data["시작일"].min() - timedelta(days=7)
    grid_end = chart_data["종료일"].max() + timedelta(days=7)
    
    if pd.notnull(grid_start) and pd.notnull(grid_end):
        c_date = grid_start
        while c_date <= grid_end:
            if c_date.weekday() == 5:
                fig.add_vrect(
                    x0=c_date, x1=c_date + timedelta(days=2),
                    fillcolor="rgba(100, 100, 100, 0.3)", layer="below", line_width=0
                )
            if c_date.weekday() == 0:
                fig.add_vline(
                    x=c_date.timestamp() * 1000, 
                    line_width=2, line_dash="solid", line_color="rgba(200, 200, 200, 0.6)"
                )
            c_date += timedelta(days=1)

    st.plotly_chart(
        fig, 
        use_container_width=True,
        config={'scrollZoom': False, 'displayModeBar': True}
    )
else:
    st.info("표시할 일정이 없습니다.")

# -----------------------------------------------------------------------------
# 6. [업무 현황 및 컨트롤 섹션]
# -----------------------------------------------------------------------------
st.divider()
st.subheader("📝 업무 현황")

# 상세 필터링
with st.expander("🔍 상세 필터링 (원하는 항목을 선택하세요)", expanded=False):
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    with f_col1: filter_project = st.multiselect("프로젝트명", options=projects_list)
    with f_col2: filter_item = st.multiselect("구분", options=items_list)
    with f_col3: filter_member = st.multiselect("담당자", options=members_list)
    with f_col4: filter_activity = st.multiselect("Activity", options=activity_list)

# 1차 필터링 적용
filtered_df = base_data.copy()
if filter_project: filtered_df = filtered_df[filtered_df["프로젝트명"].isin(filter_project)]
if filter_item: filtered_df = filtered_df[filtered_df["구분"].isin(filter_item)]
if filter_member: filtered_df = filtered_df[filtered_df["담당자"].isin(filter_member)]
if filter_activity: filtered_df = filtered_df[filtered_df["Activity"].isin(filter_activity)]

# -----------------------------------------------------------------------------
# 7. [기능 추가] 확실한 정렬 기능 (Sort)
# -----------------------------------------------------------------------------
# 헤더 클릭 정렬이 불안정한 경우를 대비한 명시적 정렬 컨트롤
col_sort1, col_sort2, col_dummy = st.columns([0.2, 0.2, 0.6])
with col_sort1:
    sort_col = st.selectbox("🗂️ 정렬 기준", ["프로젝트명", "구분", "담당자", "시작일", "종료일", "진행률"])
with col_sort2:
    sort_asc = st.toggle("오름차순 정렬", value=True)

# 2차 정렬 적용 (이 데이터가 에디터에 표시됨)
filtered_df = filtered_df.sort_values(by=sort_col, ascending=sort_asc)

# -----------------------------------------------------------------------------
# 8. 버튼 그룹 (1/3 등분)
# -----------------------------------------------------------------------------
# [수정] 3개의 컬럼을 1:1:1 비율로 생성하여 버튼이 꽉 차게 배치
col_down, col_toggle, col_print = st.columns(3)

with col_down:
    download_cols = required_cols + ["남은기간"]
    available_download_cols = [c for c in download_cols if c in data.columns]
    csv = data[available_download_cols].to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 엑셀(CSV) 다운로드", data=csv, file_name='design_schedule.csv', mime='text/csv', use_container_width=True)

with col_toggle:
    btn_text = "🙈 완료된 업무 끄기" if st.session_state.show_completed else "👁️ 완료된 업무 보기"
    if st.button(btn_text, use_container_width=True):
        st.session_state.show_completed = not st.session_state.show_completed
        st.rerun()

with col_print:
    # [복구] 인쇄 버튼
    if st.button("🖨️ 인쇄", use_container_width=True):
        components.html("<script>window.print()</script>", height=0, width=0)

# -----------------------------------------------------------------------------
# 9. 데이터 에디터
# -----------------------------------------------------------------------------
st.caption("※ 위 '정렬 기준'을 사용하여 데이터를 정렬할 수 있습니다. 수정 후 **저장**을 꼭 누르세요.")

display_cols = ["프로젝트명", "구분", "담당자", "Activity", "시작일", "종료일", "남은기간", "진행률", "진행상황"]
final_display_cols = [c for c in display_cols if c in filtered_df.columns]

edited_df = st.data_editor(
    filtered_df,
    num_rows="dynamic",
    column_config={
        "프로젝트명": st.column_config.SelectboxColumn("프로젝트명", options=projects_list, required=True),
        "구분": st.column_config.SelectboxColumn("구분", options=items_list),
        "담당자": st.column_config.SelectboxColumn("담당자", options=members_list),
        "Activity": st.column_config.SelectboxColumn("Activity", options=activity_list),
        # [수정] 라벨명 변경: 진행률(입력) -> 진행률
        "진행률": st.column_config.NumberColumn("진행률", min_value=0, max_value=100, step=5, format="%d"),
        "진행상황": st.column_config.ProgressColumn("진행상황(Bar)", format="%d%%", min_value=0, max_value=100),
        "시작일": st.column_config.DateColumn("시작일", format="YYYY-MM-DD"),
        "종료일": st.column_config.DateColumn("종료일", format="YYYY-MM-DD"),
        "남은기간": st.column_config.NumberColumn("남은기간(일)", format="%d일", disabled=True),
    },
    column_order=final_display_cols,
    use_container_width=True,
    hide_index=True,
    key="data_editor"
)

# -----------------------------------------------------------------------------
# 10. 저장 버튼
# -----------------------------------------------------------------------------
if st.button("💾 변경사항 저장하기", type="primary"):
    try:
        # 화면 수정 데이터 (ID 포함)
        save_part_df = edited_df[required_cols + ["_original_id"]]
        
        # 숨겨진 데이터 병합 (필터링 등으로 안 보이는 데이터 보존)
        visible_ids = edited_df["_original_id"].dropna().tolist()
        hidden_data = data[~data["_original_id"].isin(visible_ids)].copy()
        
        # 합치기
        save_part_df = save_part_df[required_cols]
        hidden_part_df = hidden_data[required_cols]
        
        final_save_df = pd.concat([save_part_df, hidden_part_df], ignore_index=True)
        
        # 형식 통일
        final_save_df["시작일"] = pd.to_datetime(final_save_df["시작일"]).dt.strftime("%Y-%m-%d").fillna("")
        final_save_df["종료일"] = pd.to_datetime(final_save_df["종료일"]).dt.strftime("%Y-%m-%d").fillna("")
        final_save_df["진행률"] = pd.to_numeric(final_save_df["진행률"]).fillna(0).astype(int)

        conn.update(worksheet="Sheet1", data=final_save_df)
        st.cache_data.clear()
        
        st.toast("저장되었습니다! (잠시 후 새로고침)", icon="✅")
        time.sleep(1)
        st.rerun()
        
    except Exception as e:
        st.error(f"저장 중 오류 발생: {e}")
