import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import time
import streamlit.components.v1 as components
import textwrap # 줄바꿈 처리를 위한 라이브러리

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 인쇄용 CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="디자인1본부 일정관리", layout="wide")

# 인쇄 시 적용될 CSS (표 폭 100%, 불필요한 요소 숨김)
print_css = """
<style>
@media print {
    header, footer, [data-testid="stSidebar"], [data-testid="stToolbar"], 
    .stButton, .stDownloadButton, .stExpander, .stForm, div[data-testid="stVerticalBlockBorderWrapper"] {
        display: none !important;
    }
    .main .block-container {
        max-width: 100% !important;
        width: 100% !important;
        padding: 10px !important;
        margin: 0 !important;
    }
    div[data-testid="stDataEditor"] table {
        width: 100% !important;
        font-size: 10px !important;
    }
    @page {
        size: landscape;
        margin: 0.5cm;
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

# [New] 긴 프로젝트명 줄바꿈 함수 (20% 폭 고려하여 약 15~20자마자 줄바꿈)
def wrap_labels(text, width=15):
    if pd.isna(text): return ""
    return "<br>".join(textwrap.wrap(str(text), width=width, break_long_words=True))

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
# 5. [시각화 섹션] 간트차트 (디자인 대폭 수정)
# -----------------------------------------------------------------------------
st.subheader("📊 전체 일정 (Gantt Chart)")

# 1. 필터링
if st.session_state.show_completed:
    base_data = data.copy()
else:
    base_data = data[data["진행률"] < 100].copy()

# 2. 차트용 데이터
chart_data = base_data.dropna(subset=["시작일", "종료일"]).copy()

if not chart_data.empty:
    # [New] 프로젝트명 줄바꿈 적용 (Y축 라벨용 새로운 컬럼 생성)
    chart_data["프로젝트명_줄바꿈"] = chart_data["프로젝트명"].apply(lambda x: wrap_labels(x))

    custom_colors = px.colors.qualitative.Pastel 

    # 차트 생성
    fig = px.timeline(
        chart_data, 
        x_start="시작일", x_end="종료일", 
        y="프로젝트명_줄바꿈",  # 줄바꿈 적용된 컬럼 사용
        color="담당자",
        color_discrete_sequence=custom_colors,
        hover_name="프로젝트명",
        hover_data=["구분", "Activity", "진행률", "남은기간"],
        title="프로젝트별 일정"
    )
    
    # 3. [디자인] 레이아웃 설정
    fig.update_layout(
        xaxis_title="", 
        yaxis_title="", 
        barmode='group', 
        bargap=0.2, 
        height=500, # 줄바꿈으로 인해 높이 약간 확보
        paper_bgcolor='rgb(40, 40, 40)',
        plot_bgcolor='rgb(40, 40, 40)',
        font=dict(color="white"),
        margin=dict(l=10, r=10, t=60, b=10),
        
        # [설정] 드래그 모드: Pan(이동)만 허용, 줌은 버튼으로만
        dragmode="pan", 
        
        # 범례 우측 배치
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.01
        ),
        
        # [설정] 초기 화면 3주 보이기 (오늘 -3일 ~ 오늘 +18일)
        xaxis=dict(
            range=[(today - timedelta(days=3)), (today + timedelta(days=18))]
        )
    )
    
    # 4. [디자인] X축 (날짜) 그리드 및 주말/주간 설정
    fig.update_xaxes(
        showgrid=True,
        # 1일 단위 옅은 회색 파선
        dtick=86400000.0, # 1 day in milliseconds
        gridcolor='rgba(255, 255, 255, 0.1)', 
        griddash='dot', 
        tickfont=dict(color="white"),
        side="bottom"
    )
    
    # [설정] Y축 고정 (세로 스크롤/줌 방지) 및 프로젝트 구분선
    fig.update_yaxes(
        fixedrange=True, # 세로 방향 줌/이동 잠금
        autorange="reversed",
        showticklabels=True,
        tickfont=dict(color="white", size=13),
        showgrid=True,
        # [디자인] 프로젝트 사이 구분선: 밝은 회색 굵은 실선
        gridcolor='rgba(200, 200, 200, 0.5)', 
        gridwidth=1,
        layer="below traces"
    )

    # 5. [디자인] 주말(회색톤) 및 1주일 단위(굵은선) 그리기
    # 데이터의 전체 범위 계산
    min_date = chart_data["시작일"].min() - timedelta(days=7)
    max_date = chart_data["종료일"].max() + timedelta(days=7)
    
    if pd.notnull(min_date) and pd.notnull(max_date):
        # 전체 기간을 순회하며 주말/월요일 체크
        curr_date = min_date
        while curr_date <= max_date:
            # 주말 (토, 일) 회색 배경
            if curr_date.weekday() == 5: # 토요일
                fig.add_vrect(
                    x0=curr_date, 
                    x1=curr_date + timedelta(days=2), # 월요일 0시 직전까지
                    fillcolor="rgba(100, 100, 100, 0.3)", 
                    layer="below", 
                    line_width=0
                )
            
            # 1주일 기준선 (매주 월요일) - 밝은 회색 굵은 선
            if curr_date.weekday() == 0: # 월요일
                fig.add_vline(
                    x=curr_date.timestamp() * 1000, 
                    line_width=2, 
                    line_dash="solid",
                    line_color="rgba(200, 200, 200, 0.6)"
                )
            
            curr_date += timedelta(days=1)

    # 6. 차트 출력 (스크롤 줌 비활성화 옵션 적용)
    st.plotly_chart(
        fig, 
        use_container_width=True,
        config={
            'scrollZoom': False, # [설정] 마우스 휠/핀치 줌 비활성화
            'displayModeBar': True # 상단 툴바는 표시 (버튼으로 줌 가능)
        }
    )
else:
    st.info("표시할 일정이 없습니다.")

# -----------------------------------------------------------------------------
# 6. [업무 현황 및 컨트롤 섹션]
# -----------------------------------------------------------------------------
st.divider()
st.subheader("📝 디자인 1본부 업무 현황")

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
col_down, col_toggle, col_print = st.columns(3)

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
    if st.button("🖨️ 인쇄", use_container_width=True):
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
