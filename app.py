import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 제목
# -----------------------------------------------------------------------------
st.set_page_config(page_title="디자인1본부 일정관리", layout="wide")
st.title("📅 디자인1본부 1팀 작업일정")

# -----------------------------------------------------------------------------
# 2. 구글 시트 데이터 연결 (캐시 끄기 필수)
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

# [해결 1] ttl=0 설정으로 F5 누를 때마다 무조건 새 데이터를 가져옴 (캐시 사용 안 함)
try:
    data = conn.read(worksheet="Sheet1", usecols=list(range(7)), ttl=0)
except Exception as e:
    st.error(f"⚠️ 데이터를 불러오지 못했습니다. 구글 시트 이름이 'Sheet1'인지 확인하세요.\n에러 내용: {e}")
    st.stop()

# 데이터가 비어있을 경우를 대비해 컬럼 구조 생성
if data.empty:
    data = pd.DataFrame(columns=["프로젝트명", "항목", "담당자", "Activity", "시작일", "종료일", "진행률"])

# -----------------------------------------------------------------------------
# 3. 데이터 전처리 (입력 오류 방지 및 형변환)
# -----------------------------------------------------------------------------
# 1) 날짜 변환: 에러가 나도 데이터를 삭제하지 않고 NaT(빈 날짜)로 둡니다.
data["시작일"] = pd.to_datetime(data["시작일"], errors='coerce')
data["종료일"] = pd.to_datetime(data["종료일"], errors='coerce')

# 2) [해결 2] 진행률 입력 불가 해결 (무조건 정수형으로 변환)
# 빈 값(NaN)이나 문자가 섞여 있으면 0으로 바꾸고 정수(int)로 만듭니다.
data["진행률"] = pd.to_numeric(data["진행률"], errors='coerce').fillna(0).astype(int)

# -----------------------------------------------------------------------------
# 4. [입력 섹션] 새 일정 등록
# -----------------------------------------------------------------------------
with st.expander("➕ 새 일정 등록하기 (열기/닫기)"):
    with st.form("add_task_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            p_name = st.text_input("프로젝트명")
            p_item = st.text_input("항목")
        with c2:
            p_member = st.text_input("담당자")
            p_act = st.text_input("Activity")
        with c3:
            # 날짜 입력 기본값은 오늘
            p_start = st.date_input("시작일", datetime.today())
            p_end = st.date_input("종료일", datetime.today())
        
        if st.form_submit_button("일정 추가"):
            # 저장할 때는 문자열(YYYY-MM-DD)로 변환
            new_row = pd.DataFrame([{
                "프로젝트명": p_name,
                "항목": p_item,
                "담당자": p_member,
                "Activity": p_act,
                "시작일": p_start.strftime("%Y-%m-%d"),
                "종료일": p_end.strftime("%Y-%m-%d"),
                "진행률": 0
            }])
            
            # 기존 데이터(날짜타입)를 저장용(문자타입)으로 변환 후 합치기
            save_data = data.copy()
            save_data["시작일"] = save_data["시작일"].dt.strftime("%Y-%m-%d")
            save_data["종료일"] = save_data["종료일"].dt.strftime("%Y-%m-%d")
            
            final_df = pd.concat([save_data, new_row], ignore_index=True)
            
            # 구글 시트 업데이트
            conn.update(worksheet="Sheet1", data=final_df)
            
            # [해결 3] 강제 캐시 삭제 (이게 있어야 사라지지 않음)
            st.cache_data.clear()
            st.success("추가되었습니다! 잠시 후 새로고침 됩니다.")
            st.rerun()

# -----------------------------------------------------------------------------
# 5. [시각화 섹션] 간트차트
# -----------------------------------------------------------------------------
st.subheader("📊 전체 일정 (Gantt Chart)")

# 차트 그릴 때는 날짜가 없는 데이터만 살짝 빼고 그립니다 (데이터 삭제 아님)
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
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("차트에 표시할 데이터가 없습니다. (날짜가 비어있는지 확인하세요)")

# -----------------------------------------------------------------------------
# 6. [수정 섹션] 팀원별 진행률 입력 (메인 기능)
# -----------------------------------------------------------------------------
st.divider()
st.subheader("📝 업무 현황 수정 (진행률)")

# 데이터 에디터 설정
edited_df = st.data_editor(
    data,
    num_rows="dynamic",
    column_config={
        "진행률": st.column_config.ProgressColumn(
            "진행률 (%)",
            format="%d%%",
            min_value=0,
            max_value=100,
            step=5, # 5% 단위로 움직이게 설정 (입력 편의)
        ),
        "시작일": st.column_config.DateColumn("시작일", format="YYYY-MM-DD"),
        "종료일": st.column_config.DateColumn("종료일", format="YYYY-MM-DD"),
    },
    use_container_width=True,
    key="data_editor"
)

# -----------------------------------------------------------------------------
# 7. 저장 버튼 (가장 중요)
# -----------------------------------------------------------------------------
if st.button("💾 변경사항 저장하기", type="primary"):
    try:
        # 1. 저장 전 데이터 복사
        save_df = edited_df.copy()
        
        # 2. 날짜 컬럼을 문자열(YYYY-MM-DD)로 완벽하게 변환 (NaT는 빈 문자열로)
        save_df["시작일"] = pd.to_datetime(save_df["시작일"]).dt.strftime("%Y-%m-%d").fillna("")
        save_df["종료일"] = pd.to_datetime(save_df["종료일"]).dt.strftime("%Y-%m-%d").fillna("")
        
        # 3. 진행률도 확실하게 정수형으로 유지
        save_df["진행률"] = pd.to_numeric(save_df["진행률"]).fillna(0).astype(int)

        # 4. 구글 시트에 업로드
        conn.update(worksheet="Sheet1", data=save_df)
        
        # 5. [핵심] 캐시를 비워야 F5 눌렀을 때 옛날 데이터가 안 나옴
        st.cache_data.clear()
        
        st.toast("저장 완료! 최신 상태로 업데이트됩니다.", icon="✅")
        st.rerun()
        
    except Exception as e:
        st.error(f"저장 중 오류가 발생했습니다: {e}")
