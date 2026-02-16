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
    # 모든 컬럼 읽어오기 (캐시 끄기)
    data = conn.read(worksheet="Sheet1", ttl=0)
except Exception as e:
    st.error(f"⚠️ 데이터 불러오기 실패. 구글 시트 탭 이름이 'Sheet1'인지 확인하세요.\n에러: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. 데이터 전처리
# -----------------------------------------------------------------------------
required_cols = ["프로젝트명", "공종", "담당자", "Activity", "시작일", "종료일", "진행률"]

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

# 4) 시각화용 진행상황 컬럼 복사
data["진행상황"] = data["진행률"]

# 5) 리스트 추출
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
            
            # 저장 로직
            save_data = data[required_cols].copy()
            save_data["시작일"] = save_data["시작일"].dt.strftime("%Y-%m-%d")
            save_data["종료일"] = save_data["종료일"].dt.strftime("%Y-%m-%d")
            
            final_df = pd.concat([save_data, new_row], ignore_index=True)
            conn.update(worksheet="Sheet1", data=final_df)
            st.cache_data.clear()
            st.rerun()

# -----------------------------------------------------------------------------
# 5. [필터 및 시각화 섹션]
# -----------------------------------------------------------------------------
st.subheader("📊 전체 일정 (Gantt Chart)")

# 완료된 항목 숨기기 토글
col_toggle, col_dummy = st.columns([0.3, 0.7])
with col_toggle:
    show_completed = st.toggle("✅ 완료된 업무(100%) 보기", value=False)

# 필터링 로직
if show_completed:
    filtered_data = data.copy() 
else:
    filtered_data = data[data["진행률"] < 100].copy()

# 차트용 데이터
chart_data = filtered_data.dropna(subset=["시작일", "종료일"]).copy()

if not chart_data.empty:
    fig = px.timeline(
        chart_data, 
        x_start="시작일", x_end="종료일", y="프로젝트명", 
        color="담당자",
        hover_name="프로젝트명",
        hover_data=["공종", "Activity", "진행률", "남은기간"],
        title="프로젝트별 일정"
    )
    
    # [디자인 수정] 차트 스타일링 (배경색 어둡게 설정하여 흰 글씨 부각)
    fig.update_layout(
        xaxis_title="", 
        yaxis_title="", 
        barmode='group', 
        bargap=0.1,
        height=600,
        # 차트 영역(plot)과 바깥 영역(paper) 모두 어두운 회색으로 설정
        paper_bgcolor='rgb(40, 40, 40)',
        plot_bgcolor='rgb(40, 40, 40)',
        font=dict(color="white"), # 전체 글자색 흰색
    )
    
    # [에러 수정 완료] X축 설정 (backgroundcolor 삭제됨)
    fig.update_xaxes(
        showgrid=True,
        gridcolor='rgba(255, 255, 255, 0.1)', # 세로 그리드 연하게
        tickfont=dict(color="white"), # 날짜 글씨 흰색
        side="bottom" 
    )
    
    # Y축 설정 (프로젝트명 흰색)
    fig.update_yaxes(
        autorange="reversed",
        showticklabels=True, # 프로젝트명 표시
        tickfont=dict(color="white", size=14), # 흰색 글씨
        showgrid=True, # 가로 그리드 켜기
        gridcolor='rgba(255, 255, 255, 0.3)', # 프로젝트 구분선 (실선, 투명도 조절)
        gridwidth=1,
    )

    # 분기별 구분선 (실선)
    min_date = chart_data["시작일"].min()
    max_date = chart_data["종료일"].max()
    
    if pd.notnull(min_date) and pd.notnull(max_date):
        for year in range(min_date.year, max_date.year + 2):
            for month in [1, 4, 7, 10]: 
                q_date = datetime(year, month, 1)
                fig.add_vline(
                    x=q_date.timestamp() * 1000, 
                    line_width=1, 
                    line_dash="solid", # 실선
                    line_color="rgba(255, 255, 255, 0.6)" # 약간 투명한 흰색
                )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("표시할 일정이 없습니다. (완료된 업무만 있거나 데이터가 없습니다)")

# -----------------------------------------------------------------------------
# 6. [수정 및 다운로드 섹션]
# -----------------------------------------------------------------------------
st.divider()
c_title, c_down = st.columns([0.8, 0.2])

with c_title:
    st.subheader("📝 업무 현황")
    st.caption("※ 제목(공종, 담당자 등)을 클릭하면 **정렬**됩니다.")

with c_down:
    # 엑셀 다운로드
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
final_display_cols = [c for c in display_cols if c in filtered_data.columns]

edited_df = st.data_editor(
    filtered_data[final_display_cols],
    num_rows="dynamic",
    column_config={
        "프로젝트명": st.column_config.SelectboxColumn("프로젝트명", options=projects_list, required=True),
        "공종": st.column_config.SelectboxColumn("공종", options=items_list),
        "담당자": st.column_config.SelectboxColumn("담당자", options=members_list),
        "진행률": st.column_config.NumberColumn("진행률(입력)", min_value=0, max_value=100, step=5, format="%d"),
        "진행상황": st.column_config.ProgressColumn("진행상황(Bar)", format="%d%%", min_value=0, max_value=100),
        "시작일": st.column_config.DateColumn("시작일", format="YYYY-MM-DD"),
        "종료일": st.column_config.DateColumn("종료일", format="YYYY-MM-DD"),
        "남은기간": st.column_config.NumberColumn("남은기간(일)", format="%d일", disabled=True),
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
        # 1. 화면 수정 데이터
        save_part_df = edited_df[required_cols].copy()
        
        # 2. 숨겨진 데이터 병합
        if not show_completed: 
            hidden_data = data[data["진행률"] == 100][required_cols].copy()
        else:
            hidden_data = pd.DataFrame(columns=required_cols)

        final_save_df = pd.concat([save_part_df, hidden_data], ignore_index=True)
        
        # 3. 형식 통일
        final_save_df["시작일"] = pd.to_datetime(final_save_df["시작일"]).dt.strftime("%Y-%m-%d").fillna("")
        final_save_df["종료일"] = pd.to_datetime(final_save_df["종료일"]).dt.strftime("%Y-%m-%d").fillna("")
        final_save_df["진행률"] = pd.to_numeric(final_save_df["진행률"]).fillna(0).astype(int)

        # 4. 업로드
        conn.update(worksheet="Sheet1", data=final_save_df)
        st.cache_data.clear()
        
        st.toast("저장되었습니다! (잠시 후 새로고침)", icon="✅")
        time.sleep(1)
        st.rerun()
        
    except Exception as e:
        st.error(f"저장 중 오류 발생: {e}")
