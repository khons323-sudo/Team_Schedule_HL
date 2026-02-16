import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# -----------------------------------------------------------------------------
# 1. 페이지 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="디자인1본부 일정관리", layout="wide")
st.title("📅 디자인1본부 1팀 작업일정")

# -----------------------------------------------------------------------------
# 2. 구글 시트 연결 (캐시 끄기)
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # ttl=0: 캐시 사용 안 함 (F5 누르면 즉시 갱신)
    data = conn.read(worksheet="Sheet1", usecols=list(range(7)), ttl=0)
except Exception as e:
    st.error(f"⚠️ 데이터 불러오기 실패. 구글 시트 이름이 'Sheet1'인지 확인하세요.\n에러: {e}")
    st.stop()

# 데이터가 비어있을 경우 구조 생성
if data.empty:
    data = pd.DataFrame(columns=["프로젝트명", "항목", "담당자", "Activity", "시작일", "종료일", "진행률"])

# -----------------------------------------------------------------------------
# 3. 데이터 전처리 (입력 오류 해결의 핵심)
# -----------------------------------------------------------------------------
# 1) 날짜 변환 (에러나면 NaT)
data["시작일"] = pd.to_datetime(data["시작일"], errors='coerce')
data["종료일"] = pd.to_datetime(data["종료일"], errors='coerce')

# 2) [핵심] 진행률 입력 불가 해결 로직
# 혹시 '50%' 처럼 문자열로 되어있다면 '%'를 떼어내고 숫자로 변환
if data["진행률"].dtype == 'object':
    data["진행률"] = data["진행률"].astype(str).str.replace('%', '')

# 숫자가 아닌 것들은 0으로 바꾸고, 무조건 정수(int)로 변환
data["진행률"] = pd.to_numeric(data["진행률"], errors='coerce').fillna(0).astype(int)

# -----------------------------------------------------------------------------
# 4. [입력 섹션] 새 일정 등록
# -----------------------------------------------------------------------------
with st.expander("➕ 새 일정 등록하기"):
    with st.form("add_task_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            p_name = st.text_input("프로젝트명")
            p_item = st.text_input("항목")
        with c2:
            p_member = st.text_input("담당자")
            p_act = st.text_input("Activity")
        with c3:
            p_start = st.date_input("시작일", datetime.today())
            p_end = st.date_input("종료일", datetime.today())
        
        if st.form_submit_button("일정 추가"):
            # 저장용 데이터 생성 (날짜는 문자열로)
            new_row = pd.DataFrame([{
                "프로젝트명": p_name,
                "항목": p_item,
                "담당자": p_member,
                "Activity": p_act,
                "시작일": p_start.strftime("%Y-%m-%d"),
                "종료일": p_end.strftime("%Y-%m-%d"),
                "진행률": 0
            }])
            
            # 기존 데이터 형식 맞춰서 합치기
            save_data = data.copy()
            save_data["시작일"] = save_data["시작일"].dt.strftime("%Y-%m-%d")
            save_data["종료일"] = save_data["종료일"].dt.strftime("%Y-%m-%d")
            
            final_df = pd.concat([save_data, new_row], ignore_index=True)
            
            # 업로드 및 캐시 삭제
            conn.update(worksheet="Sheet1", data=final_df)
            st.cache_data.clear()
            st.rerun()

# -----------------------------------------------------------------------------
# 5. [시각화 섹션] 간트차트 (두께 조절 + 분기별 선 추가)
# -----------------------------------------------------------------------------
st.subheader("📊 전체 일정 (Gantt Chart)")

# 차트용 데이터 (날짜 없는 행 제외)
chart_data = data.dropna(subset=["시작일", "종료일"]).copy()

if not chart_data.empty:
    fig = px.timeline(
        chart_data, 
        x_start="시작일", x_end="종료일", y="프로젝트명", 
        color="담당자", 
        hover_data=["항목", "Activity", "진행률"],
        text="Activity",
        title="프로젝트별 일정"
    )
    
    # [수정 1] 바 두께 조절 (bargap이 클수록 바가 얇아짐. 0.5는 50% 두께)
    fig.update_layout(
        xaxis_title="날짜", 
        yaxis_title="프로젝트",
        bargap=0.5 
    )
    fig.update_yaxes(autorange="reversed")

    # [수정 2] 분기별 구분선 추가 (1월, 4월, 7월, 10월)
    min_date = chart_data["시작일"].min()
    max_date = chart_data["종료일"].max()
    
    # 데이터가 존재하는 연도 범위 계산
    if pd.notnull(min_date) and pd.notnull(max_date):
        for year in range(min_date.year, max_date.year + 2):
            for month in [1, 4, 7, 10]: # 분기 시작월
                q_date = datetime(year, month, 1)
                # 차트 범위 내에 있을 때만 선 그리기
                fig.add_vline(
                    x=q_date.timestamp() * 1000, # Plotly 타임스탬프 변환
                    line_width=1, 
                    line_dash="dash", 
                    line_color="gray",
                    opacity=0.5
                )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("일정이 등록되면 여기에 차트가 표시됩니다.")

# -----------------------------------------------------------------------------
# 6. [수정 섹션] 진행률 입력 (데이터 에디터)
# -----------------------------------------------------------------------------
st.divider()
st.subheader("📝 업무 현황 수정 (진행률)")
st.caption("※ 진행률 바를 드래그하거나 숫자를 클릭해 수정하세요. 수정 후 반드시 아래 '저장' 버튼을 눌러주세요.")

edited_df = st.data_editor(
    data,
    num_rows="dynamic",
    column_config={
        "진행률": st.column_config.ProgressColumn(
            "진행률 (%)",
            format="%d%%",
            min_value=0,
            max_value=100,
            step=5,
        ),
        "시작일": st.column_config.DateColumn("시작일", format="YYYY-MM-DD"),
        "종료일": st.column_config.DateColumn("종료일", format="YYYY-MM-DD"),
    },
    use_container_width=True,
    key="data_editor" # 키 고정
)

# -----------------------------------------------------------------------------
# 7. 저장 버튼
# -----------------------------------------------------------------------------
if st.button("💾 변경사항 저장하기", type="primary"):
    try:
        save_df = edited_df.copy()
        
        # 날짜 포맷 통일 (문자열 변환)
        save_df["시작일"] = pd.to_datetime(save_df["시작일"]).dt.strftime("%Y-%m-%d").fillna("")
        save_df["종료일"] = pd.to_datetime(save_df["종료일"]).dt.strftime("%Y-%m-%d").fillna("")
        
        # [중요] 진행률 정수형 유지
        save_df["진행률"] = pd.to_numeric(save_df["진행률"]).fillna(0).astype(int)

        conn.update(worksheet="Sheet1", data=save_df)
        st.cache_data.clear() # 캐시 삭제 (데이터 사라짐 방지)
        
        st.toast("저장 완료!", icon="✅")
        st.rerun()
        
    except Exception as e:
        st.error(f"저장 중 오류 발생: {e}")
