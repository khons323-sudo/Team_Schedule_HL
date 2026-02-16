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
    data = conn.read(worksheet="Sheet1", ttl=0)
except Exception as e:
    st.error(f"⚠️ 데이터 불러오기 실패. 구글 시트 탭 이름이 'Sheet1'인지 확인하세요.\n에러: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. 데이터 전처리
# -----------------------------------------------------------------------------
required_cols = ["프로젝트명", "공종", "담당자", "Activity", "시작일", "종료일", "진행률"]

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

# 5) 드롭다운용 리스트
projects_list = sorted(data["프로젝트명"].astype(str).dropna().unique().tolist())
if "공종" in data.columns:
    items_list = sorted(data["공종"].astype(str).dropna().unique().tolist())
else:
    items_list = []
members_list = sorted(data["담당자"].astype(str).dropna().unique().tolist())

# -----------------------------------------------------------------------------
# 4. [입력 섹션] 새 일정 등록
# -----------------------------------------------------------------------------
with st.expander("➕ 새 일정 등록하기"):
    with st.form("add_task_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            p_name = st.text_input("프로젝트명")
            p_item = st.text_input("공종")
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
            
            save_data = data[required_cols].copy()
            save_data["시작일"] = save_data["시작일"].dt.strftime("%Y-%m-%d")
            save_data["종료일"] = save_data["종료일"].dt.strftime("%Y-%m-%d")
            
            final_df = pd.concat([save_data, new_row], ignore_index=True)
            conn.update(worksheet="Sheet1", data=final_df)
            st.cache_data.clear()
            st.rerun()

# -----------------------------------------------------------------------------
# 5. [시각화 섹션] 간트차트 (디자인 수정 적용)
# -----------------------------------------------------------------------------
st.subheader("📊 전체 일정 (Gantt Chart)")

chart_data = data.dropna(subset=["시작일", "종료일"]).copy()

if not chart_data.empty:
    # 1. 차트 기본 생성
    fig = px.timeline(
        chart_data, 
        x_start="시작일", x_end="종료일", y="프로젝트명", 
        color="담당자",
        hover_name="프로젝트명",
        hover_data=["공종", "Activity", "진행률", "남은기간"],
        title="프로젝트별 일정"
    )
    
    # 2. 레이아웃 디자인 수정
    fig.update_layout(
        xaxis_title="", # 하단 날짜 제목 제거 (깔끔하게)
        yaxis_title="", # 좌측 '프로젝트명' 제목 제거 (라벨은 유지)
        barmode='group', 
        bargap=0.2,
        height=600,
        # [요청] 하단 날짜 나오는 칸 Grey Tone -> Range Slider 활성화로 구현
        xaxis=dict(
            rangeslider=dict(visible=True), # 하단에 회색 톤의 범위 조절바 생성
            type="date"
        )
    )
    
    # 3. Y축 (왼쪽 프로젝트명) 설정
    fig.update_yaxes(
        autorange="reversed", # 위에서부터 순서대로
        showticklabels=True,  # [요청] 프로젝트명 글자 다시 보이게 설정
        tickfont=dict(size=12, color="black"), # 글자 크기 및 색상
        tickangle=0,          # [요청] 글자 회전 없이 가로로 똑바로
        # [요청] 팀원 구분선(파선) -> 기본 그리드를 파선으로 설정
        showgrid=True,
        gridwidth=1,
        gridcolor='lightgray',
        griddash='dash'       # 파선 (Dashed line)
    )

    # 4. [요청] 분기별(3개월) 구분선 - 점선 대신 '실선'
    min_date = chart_data["시작일"].min()
    max_date = chart_data["종료일"].max()
    
    if pd.notnull(min_date) and pd.notnull(max_date):
        for year in range(min_date.year, max_date.year + 2):
            for month in [1, 4, 7, 10]: 
                q_date = datetime(year, month, 1)
                fig.add_vline(
                    x=q_date.timestamp() * 1000, 
                    line_width=1.5,     # 선 두께
                    line_dash="solid",  # [요청] 실선(Solid)
                    line_color="#888888", # 진한 회색
                    opacity=0.5
                )

    # 5. [요청] 프로젝트 구분선 (수평 실선)
    # 프로젝트 개수만큼 반복하며 수평선 그리기
    unique_projects = chart_data["프로젝트명"].unique()
    for i in range(len(unique_projects) + 1):
        # Y축은 카테고리 데이터라 0, 1, 2... 인덱스를 가짐.
        # 프로젝트 사이사이에 선을 긋기 위해 i - 0.5 위치에 선을 그림
        fig.add_hline(
            y=i - 0.5,
            line_width=1,
            line_dash="solid", # [요청] 프로젝트 구분은 실선
            line_color="black",
            opacity=0.3
        )

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
    st.caption("※ **'진행률(입력)'**에 숫자를 입력하면 오른쪽 바가 변합니다.")

with c_down:
    download_cols = required_cols + ["남은기간"]
    available_download_cols = [c for c in download_cols if c in data.columns]
    
    csv = data[available_download_cols].to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 엑셀(CSV) 다운로드",
        data=csv,
        file_name='design_team_schedule.csv',
        mime='text/csv',
    )

# -----------------------------------------------------------------------------
# 7. 데이터 에디터
# -----------------------------------------------------------------------------
display_cols = ["프로젝트명", "공종", "담당자", "Activity", "시작일", "종료일", "남은기간", "진행률", "진행상황"]
final_display_cols = [c for c in display_cols if c in data.columns]

edited_df = st.data_editor(
    data[final_display_cols],
    num_rows="dynamic",
    column_config={
        "프로젝트명": st.column_config.SelectboxColumn("프로젝트명", options=projects_list, required=True),
        "공종": st.column_config.SelectboxColumn("공종", options=items_list),
        "담당자": st.column_config.SelectboxColumn("담당자", options=members_list),
        
        "진행률": st.column_config.NumberColumn(
            "진행률(입력)", min_value=0, max_value=100, step=5, format="%d"
        ),
        "진행상황": st.column_config.ProgressColumn(
            "진행상황(Bar)", format="%d%%", min_value=0, max_value=100
        ),
        "시작일": st.column_config.DateColumn("시작일", format="YYYY-MM-DD"),
        "종료일": st.column_config.DateColumn("종료일", format="YYYY-MM-DD"),
        "남은기간": st.column_config.NumberColumn(
            "남은기간(일)", format="%d일", disabled=True
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
        save_df = edited_df[required_cols].copy()
        
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
