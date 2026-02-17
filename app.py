import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import time
import streamlit.components.v1 as components
import textwrap 

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="디자인1본부 일정관리", layout="wide")

# 스타일 설정
st.markdown("""
    <style>
    /* 입력 폼 스타일링: 선택박스와 텍스트입력 사이 간격 좁히기 */
    div[data-testid="stForm"] .stSelectbox { margin-bottom: -15px !important; }
    div[data-testid="stForm"] .stTextInput { margin-top: 0px !important; }
    
    /* 인쇄 시 적용 CSS (기존 유지) */
    @media print {
        [data-testid="stSidebar"], [data-testid="stToolbar"], .stButton, .stDownloadButton, .stExpander, header, footer { display: none !important; }
        .main .block-container { max-width: 100% !important; width: 100% !important; padding: 1rem !important; margin: 0 !important; }
        body { -webkit-print-color-adjust: exact; }
        html, body { height: auto !important; overflow: visible !important; }
    }
    </style>
""", unsafe_allow_html=True)

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
# 3. 데이터 전처리 및 리스트 추출
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

# [New] 기존 데이터에서 리스트 추출 (빈 값 제거 및 정렬)
def get_unique_list(col_name):
    if col_name in data.columns:
        return sorted(data[col_name].astype(str).dropna().unique().tolist())
    return []

projects_list = get_unique_list("프로젝트명")
items_list = get_unique_list("구분")
members_list = get_unique_list("담당자")
activity_list = get_unique_list("Activity")

# 긴 프로젝트명 줄바꿈 함수
def wrap_labels(text, width=15):
    if pd.isna(text): return ""
    return "<br>".join(textwrap.wrap(str(text), width=width, break_long_words=True))

# -----------------------------------------------------------------------------
# 4. [입력 섹션] 새 일정 등록 (선택 + 직접입력 기능 추가)
# -----------------------------------------------------------------------------
with st.expander("➕ 새 일정 등록하기"):
    st.caption("※ 목록에서 선택하거나, 없으면 아래 입력창에 직접 입력하세요. (직접 입력 우선)")
    with st.form("add_task_form"):
        c1, c2, c3 = st.columns(3)
        
        # [수정] 콤보박스 효과 구현 (Selectbox + Textinput)
        with c1:
            sel_proj = st.selectbox("1. 프로젝트명 선택", options=["(직접 입력)"] + projects_list)
            new_proj = st.text_input("└ 또는 직접 입력", placeholder="새 프로젝트명 입력", key="new_proj")
            
            sel_item = st.selectbox("2. 구분 선택", options=["(직접 입력)"] + items_list)
            new_item = st.text_input("└ 또는 직접 입력", placeholder="예: 기획, 디자인", key="new_item")

        with c2:
            sel_member = st.selectbox("3. 담당자 선택", options=["(직접 입력)"] + members_list)
            new_member = st.text_input("└ 또는 직접 입력", placeholder="이름 입력", key="new_member")
            
            sel_act = st.selectbox("4. Activity 선택", options=["(직접 입력)"] + activity_list)
            new_act = st.text_input("└ 또는 직접 입력", placeholder="업무 내용 입력", key="new_act")

        with c3:
            p_start = st.date_input("5. 시작일", datetime.today())
            p_end = st.date_input("6. 종료일", datetime.today())
            st.markdown("<br><br>", unsafe_allow_html=True) # 여백 맞춤
            submit_btn = st.form_submit_button("일정 추가", use_container_width=True)
        
        if submit_btn:
            # [로직] 직접 입력값이 있으면 그걸 쓰고, 없으면 선택값 사용
            # "(직접 입력)"을 선택하고 입력을 안하면 빈칸이 되므로 체크 필요
            final_name = new_proj if new_proj else (sel_proj if sel_proj != "(직접 입력)" else "")
            final_item = new_item if new_item else (sel_item if sel_item != "(직접 입력)" else "")
            final_member = new_member if new_member else (sel_member if sel_member != "(직접 입력)" else "")
            final_act = new_act if new_act else (sel_act if sel_act != "(직접 입력)" else "")

            # 필수값 체크
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
# 5. [시각화 섹션] 간트차트 (2주 보기 설정)
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
    chart_data["프로젝트명_줄바꿈"] = chart_data["프로젝트명"].apply(lambda x: wrap_labels(x))
    custom_colors = px.colors.qualitative.Pastel 

    # 차트 생성
    fig = px.timeline(
        chart_data, 
        x_start="시작일", x_end="종료일", 
        y="프로젝트명_줄바꿈",
        color="담당자",
        color_discrete_sequence=custom_colors,
        hover_name="프로젝트명",
        hover_data=["구분", "Activity", "진행률", "남은기간"],
        title="프로젝트별 일정"
    )
    
    # [수정] 날짜 라벨 및 범위 설정 (2주)
    # 보여줄 기간: 오늘 기준 과거 3일 ~ 미래 11일 (총 14일 = 2주)
    view_start = today - timedelta(days=3)
    view_end = today + timedelta(days=11)
    
    tick_vals = []
    tick_text = []
    korean_days = ["월", "화", "수", "목", "금", "토", "일"]
    
    # 2주 기간 동안 날짜 생성
    curr = view_start
    while curr <= view_end:
        tick_vals.append(curr)
        # 텍스트 겹침 방지: 글자가 길면 2일 단위로 표시할 수도 있으나, 
        # 2주(14개)는 공간이 충분하므로 매일 표시하되 포맷을 깔끔하게 유지
        label = f"{curr.month}월<br>{curr.day}<br>({korean_days[curr.weekday()]})"
        tick_text.append(label)
        curr += timedelta(days=1) # 1일 단위

    # 레이아웃 설정
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
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.01),
        
        # [수정] X축 범위 고정 (2주)
        xaxis=dict(range=[view_start, view_end])
    )
    
    # X축 상세 설정
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
    
    # Y축 설정
    fig.update_yaxes(
        fixedrange=True,
        autorange="reversed",
        showticklabels=True,
        tickfont=dict(color="white", size=13),
        showgrid=True,
        gridcolor='rgba(200, 200, 200, 0.5)', 
        gridwidth=1,
        layer="below traces"
    )

    # 주말 및 주간 구분선
    grid_start = chart_data["시작일"].min() - timedelta(days=7)
    grid_end = chart_data["종료일"].max() + timedelta(days=7)
    
    if pd.notnull(grid_start) and pd.notnull(grid_end):
        c_date = grid_start
        while c_date <= grid_end:
            if c_date.weekday() == 5: # 토요일 (주말 배경)
                fig.add_vrect(
                    x0=c_date, x1=c_date + timedelta(days=2),
                    fillcolor="rgba(100, 100, 100, 0.3)", layer="below", line_width=0
                )
            if c_date.weekday() == 0: # 월요일 (주간 구분선)
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

with st.expander("🔍 상세 필터링 (원하는 항목을 선택하세요)", expanded=False):
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    with f_col1: filter_project = st.multiselect("프로젝트명", options=projects_list)
    with f_col2: filter_item = st.multiselect("구분", options=items_list)
    with f_col3: filter_member = st.multiselect("담당자", options=members_list)
    with f_col4: filter_activity = st.multiselect("Activity", options=activity_list)

filtered_df = base_data.copy()
if filter_project: filtered_df = filtered_df[filtered_df["프로젝트명"].isin(filter_project)]
if filter_item: filtered_df = filtered_df[filtered_df["구분"].isin(filter_item)]
if filter_member: filtered_df = filtered_df[filtered_df["담당자"].isin(filter_member)]
if filter_activity: filtered_df = filtered_df[filtered_df["Activity"].isin(filter_activity)]

# -----------------------------------------------------------------------------
# 7. 버튼 그룹
# -----------------------------------------------------------------------------
col_down, col_toggle, col_print = st.columns(3)

with col_down:
    download_cols = required_cols + ["남은기간"]
    available_download_cols = [c for c in download_cols if c in data.columns]
    csv = data[available_download_cols].to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 엑셀(CSV) 다운로드", data=csv, file_name='design_team_schedule.csv', mime='text/csv', use_container_width=True)

with col_toggle:
    btn_text = "🙈 완료된 업무 끄기" if st.session_state.show_completed else "👁️ 완료된 업무 보기"
    if st.button(btn_text, use_container_width=True):
        st.session_state.show_completed = not st.session_state.show_completed
        st.rerun()

with col_print:
    if st.button("🖨️ 인쇄", use_container_width=True):
        st.components.v1.html("<script>window.print()</script>", height=0, width=0)

# -----------------------------------------------------------------------------
# 8. 데이터 에디터
# -----------------------------------------------------------------------------
st.caption("※ 제목(헤더)을 클릭하면 **정렬**됩니다. 수정 후 **저장**을 꼭 누르세요.")

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
        st.cache_data.clear()
        st.toast("저장되었습니다!", icon="✅")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"저장 중 오류 발생: {e}")
