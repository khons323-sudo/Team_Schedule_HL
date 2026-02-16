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

# -----------------------------------------------------------------------------
# 2. 구글 시트 연결
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    data = conn.read(worksheet="Sheet1", usecols=list(range(7)), ttl=0)
except Exception as e:
    st.error(f"⚠️ 데이터 불러오기 실패. 구글 시트의 탭 이름이 'Sheet1'인지, 헤더에 '공종'이 있는지 확인하세요.\n에러: {e}")
    st.stop()

# 데이터가 비어있을 경우 구조 생성 (항목 -> 공종 변경)
if data.empty:
    data = pd.DataFrame(columns=["프로젝트명", "공종", "담당자", "Activity", "시작일", "종료일", "진행률"])

# -----------------------------------------------------------------------------
# 3. 데이터 전처리
# -----------------------------------------------------------------------------
# 1) 날짜 변환
data["시작일"] = pd.to_datetime(data["시작일"], errors='coerce')
data["종료일"] = pd.to_datetime(data["종료일"], errors='coerce')

# 2) [기능추가] 남은기간 계산 (오늘 기준)
today = pd.to_datetime(datetime.today().strftime("%Y-%m-%d"))
# 종료일에서 오늘을 뺀 일수(Days) 계산, 종료일이 없으면 0 처리
data["남은기간"] = (data["종료일"] - today).dt.days.fillna(0).astype(int)

# 3) 진행률 숫자 변환
if data["진행률"].dtype == 'object':
    data["진행률"] = data["진행률"].astype(str).str.replace('%', '')
data["진행률"] = pd.to_numeric(data["진행률"], errors='coerce').fillna(0).astype(int)

# 4) 시각화용 진행상황 컬럼
data["진행상황"] = data["진행률"]

# 5) 드롭다운용 리스트 추출 (공종 반영)
projects_list = sorted(data["프로젝트명"].dropna().unique().tolist())
# '공종' 컬럼이 있는지 확인 후 리스트 생성
if "공종" in data.columns:
    items_list = sorted(data["공종"].dropna().unique().tolist())
else:
    items_list = []
members_list = sorted(data["담당자"].dropna().unique().tolist())

# -----------------------------------------------------------------------------
# 4. [입력 섹션] 새 일정 등록
# -----------------------------------------------------------------------------
with st.expander("➕ 새 일정 등록하기"):
    with st.form("add_task_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            p_name = st.text_input("프로젝트명")
            p_item = st.text_input("공종") # 항목 -> 공종 변경
        with c2:
            p_member = st.text_input("담당자")
            p_act = st.text_input("Activity")
        with c3:
            p_start = st.date_input("시작일", datetime.today())
            p_end = st.date_input("종료일", datetime.today())
        
        if st.form_submit_button("일정 추가"):
            new_row = pd.DataFrame([{
                "프로젝트명": p_name,
                "공종": p_item,
                "담당자": p_member,
                "Activity": p_act,
                "시작일": p_start.strftime("%Y-%m-%d"),
                "종료일": p_end.strftime("%Y-%m-%d"),
                "진행률": 0
            }])
            
            # 저장할 때는 '진행상황', '남은기간' 등 계산된 컬럼 제외
            save_cols = ["프로젝트명", "공종", "담당자", "Activity", "시작일", "종료일", "진행률"]
            # 기존 데이터 형식 맞추기
            save_data = data[save_cols].copy()
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

chart_data = data.dropna(subset=["시작일", "종료일"]).copy()

if not chart_data.empty:
    fig = px.timeline(
        chart_data, 
        x_start="시작일", x_end="종료일", y="프로젝트명", 
        color="담당자",
        hover_name="프로젝트명",
        # 항목 -> 공종 변경
        hover_data=["공종", "Activity", "진행률", "남은기간"],
        title="프로젝트별 일정"
    )
    
    fig.update_layout(
        xaxis_title="날짜", 
        yaxis_title="", 
        barmode='group', 
        bargap=0.1,
        height=600
    )
    
    fig.update_yaxes(
        autorange="reversed",
        showticklabels=False, 
        visible=True 
    )

    # 분기별 구분선
    min_date = chart_data["시작일"].min()
    max_date = chart_data["종료일"].max()
    
    if pd.notnull(min_date) and pd.notnull(max_date):
        for year in range(min_date.year, max_date.year + 2):
            for month in [1, 4, 7, 10]: 
                q_date = datetime(year, month, 1)
                fig.add_vline(x=q_date.timestamp() * 1000, line_width=1, line_dash="dash", line_color="lightgray")

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("일정이 등록되면 여기에 차트가 표시됩니다.")

# -----------------------------------------------------------------------------
# 6. [수정 및 다운로드 섹션]
# -----------------------------------------------------------------------------
st.divider()
c_title, c_down = st.columns([0.8, 0.2])

with c_title:
    st.subheader("📝 업무 현황 수정")
    st.caption("※ **'남은기간'**은 종료일에 맞춰 자동 계산됩니다.")

with c_down:
    # 엑셀 다운로드 (계산된 컬럼 제외하고 원본만)
    save_cols = ["프로젝트명", "공종", "담당자", "Activity", "시작일", "종료일", "진행률"]
    csv = data[save_cols].to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 엑셀(CSV) 다운로드",
        data=csv,
        file_name='design_team_schedule.csv',
        mime='text/csv',
    )

# -----------------------------------------------------------------------------
# 7. 데이터 에디터
# -----------------------------------------------------------------------------
# 컬럼 순서 재배치 (남은기간을 종료일 옆으로)
display_cols = ["프로젝트명", "공종", "담당자", "Activity", "시작일", "종료일", "남은기간", "진행률", "진행상황"]
# 데이터에 없는 컬럼이 있으면 에러나므로 교집합만 사용
final_display_cols = [c for c in display_cols if c in data.columns]

edited_df = st.data_editor(
    data[final_display_cols],
    num_rows="dynamic",
    column_config={
        "프로젝트명": st.column_config.SelectboxColumn("프로젝트명", options=projects_list, required=True),
        # 항목 -> 공종 변경
        "공종": st.column_config.SelectboxColumn("공종", options=items_list),
        "담당자": st.column_config.SelectboxColumn("담당자", options=members_list),
        
        "진행률": st.column_config.NumberColumn(
            "진행률(입력)", min_value=0, max_value=100, step=5, format="%d"
        ),
        "진행상황": st.column_config.ProgressColumn(
            "진행상황(Bar)", format="%d%%", min_value=0, max_value=100, disabled=True
        ),
        "시작일": st.column_config.DateColumn("시작일", format="YYYY-MM-DD"),
        "종료일": st.column_config.DateColumn("종료일", format="YYYY-MM-DD"),
        
        # [기능추가] 남은기간 (숫자, 수정불가)
        "남은기간": st.column_config.NumberColumn(
            "남은기간(일)", 
            help="종료일까지 남은 일수입니다 (음수는 지남)",
            format="%d일",
            disabled=True # 수정 불가능 (자동계산)
        ),
    },
    use_container_width=True,
    hide_index=True,
    key="data_editor"
)

# -----------------------------------------------------------------------------
# 8. 저장 버튼
# -----------------------------------------------------------------------------
if st.button("💾 변경사항 저장하기", type="primary"):
    try:
        # 저장할 때는 '진행상황', '남은기간' 제거
        save_cols = ["프로젝트명", "공종", "담당자", "Activity", "시작일", "종료일", "진행률"]
        save_df = edited_df[save_cols].copy()
        
        save_df["시작일"] = pd.to_datetime(save_df["시작일"]).dt.strftime("%Y-%m-%d").fillna("")
        save_df["종료일"] = pd.to_datetime(save_df["종료일"]).dt.strftime("%Y-%m-%d").fillna("")
        save_df["진행률"] = pd.to_numeric(save_df["진행률"]).fillna(0).astype(int)

        conn.update(worksheet="Sheet1", data=save_df)
        st.cache_data.clear()
        
        st.toast("저장되었습니다! (잠시 후 새로고침)", icon="✅")
        time.sleep(1)
        st.rerun()
        
    except Exception as e:
        st.error(f"저장 중 오류 발생: {e}")
