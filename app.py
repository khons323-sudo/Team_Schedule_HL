import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import time

# -----------------------------------------------------------------------------
# 1. 페이지 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="디자인1본부 일정관리", layout="wide")
st.title("📅 디자인1본부 1팀 작업일정")

# 세션 상태 초기화
if 'show_completed' not in st.session_state:
    st.session_state.show_completed = False

# -----------------------------------------------------------------------------
# 2. 구글 시트 연결
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # 모든 컬럼 읽어오기 (캐시 끄기)
    data = conn.read(worksheet="Sheet1", ttl=0)
except Exception as e:
    st.error(f"⚠️ 데이터 불러오기 실패. 구글 시트 탭 이름이 'Sheet1'인지 확인하세요.\n에러: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. 데이터 전처리
# -----------------------------------------------------------------------------
required_cols = ["프로젝트명", "구분", "담당자", "Activity", "시작일", "종료일", "진행률"]

# 데이터가 비어있거나 컬럼이 모자랄 경우 처리
if data.empty:
    for col in required_cols:
        data[col] = ""
    data["진행률"] = 0

# 1) 날짜 변환
data["시작일"] = pd.to_datetime(data["시작일"], errors='coerce')
data["종료일"] = pd.to_datetime(data["종료일"], errors='coerce')

# 2) 남은기간 계산
today = pd.to_datetime(datetime.today().strftime("%Y-%m-%d"))
data["남은기간"] = (data["종료일"] - today).dt.days.fillna(0).astype(int)

# 3) 진행률 숫자 변환
if "진행률" in data.columns and data["진행률"].dtype == 'object':
    data["진행률"] = data["진행률"].astype(str).str.replace('%', '')

data["진행률"] = pd.to_numeric(data["진행률"], errors='coerce').fillna(0).astype(int)

# 4) 시각화용 진행상황 컬럼
data["진행상황"] = data["진행률"]

# 5) [중요] 필터링 후 저장 시 데이터 유실 방지를 위한 고유 ID(인덱스) 부여
# (데이터프레임의 인덱스를 별도 컬럼으로 보존)
data["_original_id"] = data.index

# 6) 리스트 추출 (옵션용)
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
            
            # 저장 시에는 _original_id 제외하고 저장
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

# 2. 차트용 데이터 (날짜 필수)
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
        legend=dict(orientation="h", y=1.1)
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

# -----------------------------------------------------------------------------
# [요청] 상세 필터링 기능 (헤더 클릭 대신 상단에 배치)
# -----------------------------------------------------------------------------
with st.expander("🔍 상세 필터링 (원하는 항목을 선택하여 데이터를 찾으세요)", expanded=False):
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    with f_col1:
        filter_project = st.multiselect("프로젝트명", options=projects_list)
    with f_col2:
        filter_item = st.multiselect("구분", options=items_list)
    with f_col3:
        filter_member = st.multiselect("담당자", options=members_list)
    with f_col4:
        filter_activity = st.multiselect("Activity", options=activity_list)

# 필터 로직 적용
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
# 7. 버튼 그룹 (다운로드 & 완료업무 토글)
# -----------------------------------------------------------------------------
col_down, col_btn, col_blank = st.columns([0.2, 0.2, 0.6])

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

with col_btn:
    # 완료된 업무 보기/끄기 토글 버튼
    btn_text = "🙈 완료된 업무 끄기" if st.session_state.show_completed else "👁️ 완료된 업무 보기"
    
    if st.button(btn_text, use_container_width=True):
        st.session_state.show_completed = not st.session_state.show_completed
        st.rerun()

# -----------------------------------------------------------------------------
# 8. 데이터 에디터
# -----------------------------------------------------------------------------
st.caption("※ 제목(헤더)을 클릭하면 **오름차순/내림차순 정렬**이 가능합니다. 필터링은 위 '🔍 상세 필터링'을 이용하세요.")

# 화면에 표시할 컬럼 지정
display_cols = ["프로젝트명", "구분", "담당자", "Activity", "시작일", "종료일", "남은기간", "진행률", "진행상황"]
# _original_id는 편집기에서는 숨겨야 함 (데이터 추적용)
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
    column_order=final_display_cols, # 표시 순서 강제 및 _original_id 숨김
    use_container_width=True,
    hide_index=True,
    key="data_editor"
)

# -----------------------------------------------------------------------------
# 9. 저장 버튼 (안전한 저장 로직)
# -----------------------------------------------------------------------------
if st.button("💾 변경사항 저장하기", type="primary"):
    try:
        # 1. 수정된 데이터 (화면에 보이는 데이터)
        # 여기서 필요한 컬럼 + 추적용 ID만 가져옴
        cols_to_save = required_cols + ["_original_id"]
        
        # 새로 추가된 행은 _original_id가 NaN일 것임
        # edited_df에는 사용자가 수정한 내용이 들어있음
        
        # 2. 숨겨져 있던 데이터 찾기
        # 전체 원본 데이터(data) 중에서, 현재 편집된 데이터(edited_df)에 없는 행들을 찾아야 함.
        # 기준은 _original_id 사용
        
        # 현재 편집창에 있는 ID 목록
        visible_ids = edited_df["_original_id"].dropna().tolist()
        
        # 숨겨진 데이터 = 원본 데이터 중 ID가 visible_ids에 없는 것
        hidden_data = data[~data["_original_id"].isin(visible_ids)].copy()
        
        # 3. 데이터 병합 (수정된 데이터 + 숨겨진 데이터)
        # 저장할 때는 _original_id 제거하고 순수 데이터만 저장
        save_part_df = edited_df[required_cols]
        hidden_part_df = hidden_data[required_cols]
        
        final_save_df = pd.concat([save_part_df, hidden_part_df], ignore_index=True)
        
        # 4. 형식 통일
        final_save_df["시작일"] = pd.to_datetime(final_save_df["시작일"]).dt.strftime("%Y-%m-%d").fillna("")
        final_save_df["종료일"] = pd.to_datetime(final_save_df["종료일"]).dt.strftime("%Y-%m-%d").fillna("")
        final_save_df["진행률"] = pd.to_numeric(final_save_df["진행률"]).fillna(0).astype(int)

        # 5. 업로드
        conn.update(worksheet="Sheet1", data=final_save_df)
        st.cache_data.clear()
        
        st.toast("저장되었습니다! (잠시 후 새로고침)", icon="✅")
        time.sleep(1)
        st.rerun()
        
    except Exception as e:
        st.error(f"저장 중 오류 발생: {e}")
