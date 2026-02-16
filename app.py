import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import time
import streamlit.components.v1 as components

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 인쇄용 CSS (대폭 수정됨)
# -----------------------------------------------------------------------------
st.set_page_config(page_title="디자인1본부 일정관리", layout="wide")

# [수정] 인쇄 시 빈 페이지/잘림 방지를 위한 강력한 CSS
print_css = """
<style>
@media print {
    /* 1. Streamlit 기본 UI 완벽하게 숨기기 */
    header, footer, aside, 
    [data-testid="stSidebar"], [data-testid="stToolbar"], 
    .stButton, .stDownloadButton, .stExpander, .stForm, 
    div[data-testid="stVerticalBlockBorderWrapper"],
    button {
        display: none !important;
    }

    /* 2. 배경과 글자색 강제 조정 (잉크 절약 및 가독성 확보) */
    body, .stApp, .block-container, div[data-testid="stDataEditor"] {
        background-color: white !important;
        color: black !important;
    }
    
    /* 표 안의 글자도 검은색으로 강제 */
    div[data-testid="stDataEditor"] * {
        color: black !important;
        font-weight: 500 !important;
    }

    /* 3. 메인 콘텐츠 강제 확장 (스크롤 해제하여 전체 출력) */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        overflow: visible !important;
        height: auto !important;
        visibility: visible !important;
    }

    /* 4. 콘텐츠 영역 넓이 100% 및 여백 제거 */
    .block-container {
        max-width: 100% !important;
        width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    /* 5. 페이지 설정 */
    @page {
        size: landscape; /* 가로 방향 */
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

# 시각화용 진행상황 컬럼
data["진행상황"] = data["진행률"]

# 고유 ID 부여
data["_original_id"] = data.index

# 리스트 추출
projects_list = sorted(data["프로젝트명"].astype(str).dropna().unique().tolist())
if "구분" in data.columns:
    items_list = sorted(data["구분"].astype(str).dropna().unique().tolist())
else:
    items_list = []
members_list = sorted(data["담당자"].astype(str).dropna().unique().tolist())
activity_list = sorted(data["Activity"].astype(str).dropna().unique().tolist())

# -----------------------------------------------------------------------------
# 4. [입력 섹션] 새 일정 등록
# -----------------------------------------------------------------------------
with st.expander("➕ 새 일정 등록하기"):
    with st.form("add_task_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            p_name = st.text_input("프로젝트명")
            p_item = st.text_input("구분")
        with c2:
            p_member = st.text_input("담당자")
            p_act = st.text_input("Activity")
        with c3:
            p_start = st.date_input("시작일", datetime.today())
            p_end = st.date_input("종료일", datetime.today())
        
        if st.form_submit_button("일정 추가"):
            new_row = pd.DataFrame([{
                "프로젝트명": p_name,
                "구분": p_item,
                "담당자": p_member,
                "Activity": p_act,
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
st.subheader("📊 전체 일정 (Gantt Chart)")

# 1. 완료된 업무 필터링
if st.session_state.show_completed:
    base_data = data.copy()
else:
    base_data = data[data["진행률"] < 100].copy()

# 2. 차트용 데이터
chart_data = base_data.dropna(subset=["시작일", "종료일"]).copy()

if not chart_data.empty:
    custom_colors = px.colors.qualitative.Pastel 

    fig = px.timeline(
        chart_data, 
        x_start="시작일", x_end="종료일", y="프로젝트명", 
        color="담당자",
        color_discrete_sequence=custom_colors,
        hover_name="프로젝트명",
        hover_data=["구분", "Activity", "진행률", "남은기간"],
        title="프로젝트별 일정"
    )
    
    # 차트 레이아웃
    fig.update_layout(
        xaxis_title="", 
        yaxis_title="", 
        barmode='group', 
        bargap=0.2, 
        height=400, 
        paper_bgcolor='rgb(40, 40, 40)',
        plot_bgcolor='rgb(40, 40, 40)',
        font=dict(color="white"),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.01
        )
    )
    
    fig.update_xaxes(
        showgrid=True,
        gridcolor='rgba(255, 255, 255, 0.1)',
        tickfont=dict(color="white"),
        side="bottom" 
    )
    
    fig.update_yaxes(
        autorange="reversed",
        showticklabels=True,
        tickfont=dict(color="white", size=14),
        showgrid=True,
        gridcolor='rgba(255, 255, 255, 0.3)',
        gridwidth=1,
        layer="below traces"
    )

    # 분기별 구분선
    min_date = chart_data["시작일"].min()
    max_date = chart_data["종료일"].max()
    
    if pd.notnull(min_date) and pd.notnull(max_date):
        for year in range(min_date.year, max_date.year + 2):
            for month in [1, 4, 7, 10]: 
                q_date = datetime(year, month, 1)
                fig.add_vline(
                    x=q_date.timestamp() * 1000, 
                    line_width=1, 
                    line_dash="solid",
                    line_color="rgba(255, 255, 255, 0.6)"
                )

    st.plotly_chart(fig, use_container_width=True)
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
    with f_col1:
        filter_project = st.multiselect("프로젝트명", options=projects_list)
    with f_col2:
        filter_item = st.multiselect("구분", options=items_list)
    with f_col3:
        filter_member = st.multiselect("담당자", options=members_list)
    with f_col4:
        filter_activity = st.multiselect("Activity", options=activity_list)

# 필터 로직
filtered_df = base_data.copy()

if filter_project:
    filtered_df = filtered_df[filtered_df["프로젝트명"].isin(filter_project)]
if filter_item:
    filtered_df = filtered_df[filtered_df["구분"].isin(filter_item)]
if filter_member:
    filtered_df = filtered_df[filtered_df["담당자"].isin(filter_member)]
if filter_activity:
    filtered_df = filtered_df[filtered_df["Activity"].isin(filter_activity)]

# -----------------------------------------------------------------------------
# 7. 버튼 그룹
# -----------------------------------------------------------------------------
col_down, col_toggle, col_print, col_blank = st.columns([0.2, 0.2, 0.15, 0.45])

with col_down:
    # 엑셀 다운로드
    download_cols = required_cols + ["남은기간"]
    available_download_cols = [c for c in download_cols if c in data.columns]
    csv = data[available_download_cols].to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 엑셀(CSV) 다운로드",
        data=csv,
        file_name='design_team_schedule.csv',
        mime='text/csv',
        use_container_width=True
    )

with col_toggle:
    # 완료된 업무 보기/끄기
    btn_text = "🙈 완료된 업무 끄기" if st.session_state.show_completed else "👁️ 완료된 업무 보기"
    if st.button(btn_text, use_container_width=True):
        st.session_state.show_completed = not st.session_state.show_completed
        st.rerun()

with col_print:
    # 인쇄 버튼
    if st.button("🖨️ 페이지 인쇄", use_container_width=True):
        st.components.v1.html("<script>window.print()</script>", height=0, width=0)

# -----------------------------------------------------------------------------
# 8. 데이터 에디터
# -----------------------------------------------------------------------------
st.caption("※ 제목(헤더)을 클릭하면 **정렬**됩니다. 수정 후 **저장**을 꼭 누르세요.")

display_cols = ["프로젝트명", "구분", "담당자", "Activity", "시작일", "종료일", "남은기간", "진행률", "진행상황"]
final_display_cols = [c for c in display_cols if c in filtered_df.columns]

# 에디터 표시
edited_df = st.data_editor(
    filtered_df,
    num_rows="dynamic",
    column_config={
        "프로젝트명": st.column_config.SelectboxColumn("프로젝트명", options=projects_list, required=True),
        "구분": st.column_config.SelectboxColumn("구분", options=items_list),
        "담당자": st.column_config.SelectboxColumn("담당자", options=members_list),
        "Activity": st.column_config.SelectboxColumn("Activity", options=activity_list),
        
        "진행률": st.column_config.NumberColumn("진행률(입력)", min_value=0, max_value=100, step=5, format="%d"),
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
# 9. 저장 버튼
# -----------------------------------------------------------------------------
if st.button("💾 변경사항 저장하기", type="primary"):
    try:
        # 화면 수정 데이터
        save_part_df = edited_df[required_cols + ["_original_id"]]
        
        # 숨겨진 데이터 병합
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

        # 업로드
        conn.update(worksheet="Sheet1", data=final_save_df)
        st.cache_data.clear()
        
        st.toast("저장되었습니다! (잠시 후 새로고침)", icon="✅")
        time.sleep(1)
        st.rerun()
        
    except Exception as e:
        st.error(f"저장 중 오류 발생: {e}")
