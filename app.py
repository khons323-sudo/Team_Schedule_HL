import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta, date
import time
import textwrap

# -----------------------------------------------------------------------------
# 1. 페이지 설정 (반드시 맨 처음에 위치)
# -----------------------------------------------------------------------------
st.set_page_config(page_title="디자인1본부 일정관리", layout="wide")

# CSS 스타일링
st.markdown("""
<style>
    .block-container { padding-top: 1rem !important; padding-bottom: 3rem !important; }
    div[data-testid="stForm"] .stSelectbox { margin-bottom: -15px !important; }
    div[data-testid="stForm"] .stTextInput { margin-top: 5px !important; }
    
    @media print {
        header, footer, aside, .stButton, .stDownloadButton, .stExpander, .stForm, 
        div[data-testid="stSidebar"], div[data-testid="stToolbar"], .no-print,
        div[data-testid="stPopover"] { display: none !important; }
        body, .stApp { background-color: white !important; color: black !important; }
        .main .block-container { max-width: 100% !important; width: 100% !important; margin: 0; padding: 0; }
        div[data-testid="stDataEditor"] table { font-size: 10px !important; border: 1px solid #000; }
        div[data-testid="stDataEditor"] th { background-color: #eee !important; color: black !important; }
    }
</style>
""", unsafe_allow_html=True)

st.title("📅 디자인1본부 1팀 일정")

# -----------------------------------------------------------------------------
# 2. 데이터 로드 및 전처리 (핵심 수정 부분)
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60) # 캐시 시간 짧게 조정
def load_data():
    try:
        # 데이터 읽기
        df = conn.read(worksheet="Sheet1")
        return df
    except Exception:
        # 실패 시 빈 프레임
        return pd.DataFrame(columns=["프로젝트명", "구분", "담당자", "Activity", "시작일", "종료일", "진행률"])

def clean_data(df):
    # 1. 필수 컬럼 보장
    required_cols = ["프로젝트명", "구분", "담당자", "Activity", "시작일", "종료일", "진행률"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    # 2. 결측치 처리
    df = df.fillna("")
    
    # 3. 진행률 숫자 변환
    if df["진행률"].dtype == 'object':
        df["진행률"] = df["진행률"].astype(str).str.replace('%', '').replace('', '0')
    df["진행률"] = pd.to_numeric(df["진행률"], errors='coerce').fillna(0).astype(int)

    # 4. [중요] 날짜 변환 (datetime64 -> datetime.date)
    # NaT(빈 날짜)가 있으면 에디터가 멈추므로 None으로 확실히 변환
    def to_date_obj(x):
        try:
            dt = pd.to_datetime(x)
            if pd.isna(dt): return None
            return dt.date()
        except:
            return None

    df["시작일_obj"] = df["시작일"].apply(to_date_obj)
    df["종료일_obj"] = df["종료일"].apply(to_date_obj)
    
    # 계산용 컬럼
    today = date.today()
    df["남은기간"] = df.apply(lambda row: (row["종료일_obj"] - today).days if row["종료일_obj"] else 0, axis=1)
    df["진행상황"] = df["진행률"] # Bar 표시용 복사

    return df

# 세션 상태 초기화
if 'data_loaded' not in st.session_state:
    raw = load_data()
    st.session_state['df'] = clean_data(raw)
    st.session_state['data_loaded'] = True
    st.session_state['show_completed'] = False

# 항상 최신 상태의 DataFrame 사용
df_main = st.session_state['df'].copy()

# 리스트 추출
def get_options(col):
    return sorted([x for x in df_main[col].unique() if x and str(x).strip() != ""])

proj_list = get_options("프로젝트명")
item_list = get_options("구분")
member_list = get_options("담당자")
act_list = get_options("Activity")

# -----------------------------------------------------------------------------
# 3. 간트차트 시각화
# -----------------------------------------------------------------------------
# 차트 데이터 필터링
chart_df = df_main.dropna(subset=["시작일_obj", "종료일_obj"]).copy()
if not st.session_state['show_completed']:
    chart_df = chart_df[chart_df["진행률"] < 100]

if not chart_df.empty:
    # 정렬
    chart_df = chart_df.sort_values(by=["프로젝트명", "시작일_obj"], ascending=[True, False]).reset_index(drop=True)
    
    # 텍스트 줄바꿈 함수
    def wrap(t): return "<br>".join(textwrap.wrap(str(t), width=12))
    
    # 프로젝트명 중복 제거 표시
    disp_names = []
    prev = None
    for nm in chart_df["프로젝트명"]:
        disp_names.append(wrap(nm) if nm != prev else "")
        prev = nm
        
    num_rows = len(chart_df)
    height = max(500, num_rows * 40 + 100)
    
    fig = make_subplots(
        rows=1, cols=5, shared_yaxes=True, horizontal_spacing=0.01,
        column_widths=[0.15, 0.07, 0.07, 0.07, 0.64],
        subplot_titles=("프로젝트", "구분", "담당자", "Activity", "일정"),
        specs=[[{"type": "scatter"}]*4 + [{"type": "xy"}]]
    )

    y_pos = list(range(num_rows))
    
    # 텍스트 컬럼들
    common = dict(mode="text", textfont=dict(size=11, color="black"))
    fig.add_trace(go.Scatter(x=[0]*num_rows, y=y_pos, text=disp_names, textposition="middle right", **common), 1, 1)
    fig.add_trace(go.Scatter(x=[0.5]*num_rows, y=y_pos, text=chart_df["구분"], textposition="middle center", **common), 1, 2)
    fig.add_trace(go.Scatter(x=[0.5]*num_rows, y=y_pos, text=chart_df["담당자"], textposition="middle center", **common), 1, 3)
    fig.add_trace(go.Scatter(x=[0]*num_rows, y=y_pos, text=chart_df["Activity"].apply(wrap), textposition="middle right", **common), 1, 4)

    # 간트 바
    for i, row in chart_df.iterrows():
        # datetime.date를 datetime으로 변환 (timestamp 사용 위해)
        start_ts = datetime.combine(row["시작일_obj"], datetime.min.time()).timestamp() * 1000
        end_ts = datetime.combine(row["종료일_obj"], datetime.min.time()).timestamp() * 1000
        duration = end_ts - start_ts
        days = (row["종료일_obj"] - row["시작일_obj"]).days + 1
        
        fig.add_trace(go.Bar(
            base=[start_ts], x=[duration], y=[i], orientation='h',
            marker_color="skyblue" if row["진행률"] < 100 else "lightgrey",
            text=f"{days}일 / {row['진행률']}%", textposition='inside',
            hoverinfo="text", hovertext=f"{row['프로젝트명']}: {row['시작일_obj']} ~ {row['종료일_obj']}"
        ), 1, 5)

    # 축 설정
    today_ts = datetime.now().timestamp() * 1000
    fig.add_vline(x=today_ts, line_dash="dash", line_color="red", row=1, col=5)
    
    fig.update_xaxes(type="date", side="top", row=1, col=5)
    for c in range(1, 5): 
        fig.update_xaxes(showgrid=False, showticklabels=False, row=1, col=c)
        fig.update_yaxes(showgrid=False, showticklabels=False, row=1, col=c)
    fig.update_yaxes(showticklabels=False, fixedrange=True, row=1, col=5)
    
    fig.update_layout(height=height, margin=dict(t=80, b=20, l=10, r=10), showlegend=False, paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("표시할 일정이 없습니다.")

# -----------------------------------------------------------------------------
# 4. 입력 폼 (단순화)
# -----------------------------------------------------------------------------
st.markdown("### ➕ 일정 추가")
with st.expander("입력 양식 열기", expanded=False):
    with st.form("input_form"):
        c1, c2, c3 = st.columns(3)
        
        # 입력 헬퍼
        def input_ui(label, options, k):
            sel = st.selectbox(f"{label} 선택", [""] + options, key=f"s_{k}")
            txt = st.text_input(f"{label} 직접입력", key=f"t_{k}")
            return sel, txt

        with c1:
            p_sel, p_txt = input_ui("프로젝트", proj_list, "proj")
            i_sel, i_txt = input_ui("구분", item_list, "item")
        with c2:
            m_sel, m_txt = input_ui("담당자", member_list, "memb")
            a_sel, a_txt = input_ui("Activity", act_list, "act")
        with c3:
            d_start = st.date_input("시작일", date.today())
            d_end = st.date_input("종료일", date.today())
            st.write("")
            btn = st.form_submit_button("추가하기", type="primary", use_container_width=True)

        if btn:
            final_p = p_txt if p_txt else p_sel
            final_i = i_txt if i_txt else i_sel
            final_m = m_txt if m_txt else m_sel
            final_a = a_txt if a_txt else a_sel
            
            if not final_p:
                st.error("프로젝트명을 입력해주세요.")
            else:
                new_data = {
                    "프로젝트명": final_p, "구분": final_i, "담당자": final_m, "Activity": final_a,
                    "시작일": d_start.strftime("%Y-%m-%d"), "종료일": d_end.strftime("%Y-%m-%d"),
                    "진행률": 0
                }
                # 현재 DataFrame에 추가 후 즉시 저장 로직으로 이동
                temp_df = st.session_state['df'].copy()
                # 원본 포맷(문자열)으로 맞추기 위해 변환
                temp_save_df = pd.DataFrame([new_data])
                
                # 기존 데이터도 문자열로 변환하여 병합 (형식 통일)
                current_raw = temp_df.drop(columns=["시작일_obj", "종료일_obj", "남은기간", "진행상황"])
                final_save = pd.concat([current_raw, temp_save_df], ignore_index=True)
                
                conn.update(worksheet="Sheet1", data=final_save)
                st.cache_data.clear() # 캐시 삭제
                del st.session_state['data_loaded'] # 재로드 트리거
                st.rerun()

# -----------------------------------------------------------------------------
# 5. 데이터 에디터 (수정 및 저장)
# -----------------------------------------------------------------------------
st.markdown("---")
col_ctrl1, col_ctrl2 = st.columns([0.8, 0.2])
with col_ctrl2:
    check_completed = st.checkbox("완료된 항목 보기", value=st.session_state['show_completed'])
    if check_completed != st.session_state['show_completed']:
        st.session_state['show_completed'] = check_completed
        st.rerun()

# 에디터용 데이터 준비
edit_target = df_main.copy()
if not st.session_state['show_completed']:
    edit_target = edit_target[edit_target["진행률"] < 100]

# 컬럼 순서 및 설정
display_cols = ["프로젝트명", "구분", "담당자", "Activity", "시작일_obj", "종료일_obj", "진행률", "진행상황", "남은기간"]

edited = st.data_editor(
    edit_target,
    column_order=display_cols,
    column_config={
        "프로젝트명": st.column_config.TextColumn(required=True),
        "구분": st.column_config.SelectboxColumn(options=item_list),
        "담당자": st.column_config.SelectboxColumn(options=member_list),
        "Activity": st.column_config.SelectboxColumn(options=act_list),
        "시작일_obj": st.column_config.DateColumn("시작일", format="YYYY-MM-DD", required=True),
        "종료일_obj": st.column_config.DateColumn("종료일", format="YYYY-MM-DD", required=True),
        "진행률": st.column_config.NumberColumn(min_value=0, max_value=100),
        "진행상황": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d%%"),
        "남은기간": st.column_config.NumberColumn(disabled=True)
    },
    hide_index=True,
    use_container_width=True,
    num_rows="fixed", # 무한로딩 방지를 위해 동적 행 추가 비활성화 (위의 폼 사용 유도)
    key="editor"
)

if st.button("💾 변경사항 저장 (전체 덮어쓰기)", type="primary"):
    with st.spinner("저장 중..."):
        # 1. 원본 데이터 복사
        final_df = st.session_state['df'].copy()
        
        # 2. 수정된 데이터 반영 (인덱스 기준 업데이트)
        # edited는 필터링된 뷰일 수 있으므로 인덱스를 이용해 원본에 업데이트
        final_df.update(edited)
        
        # 3. 저장용 포맷으로 변환 (Date Obj -> String)
        save_df = final_df.copy()
        
        def date_to_str(d):
            if isinstance(d, date): return d.strftime("%Y-%m-%d")
            if isinstance(d, datetime): return d.strftime("%Y-%m-%d")
            return str(d) if d else ""

        save_df["시작일"] = save_df["시작일_obj"].apply(date_to_str)
        save_df["종료일"] = save_df["종료일_obj"].apply(date_to_str)
        
        # 불필요한 임시 컬럼 제거
        save_cols = ["프로젝트명", "구분", "담당자", "Activity", "시작일", "종료일", "진행률"]
        save_df = save_df[save_cols]
        
        # 4. 구글 시트 업데이트
        conn.update(worksheet="Sheet1", data=save_df)
        
        # 5. 상태 초기화 및 리로드
        st.cache_data.clear()
        del st.session_state['data_loaded']
        st.success("저장 완료!")
        time.sleep(1)
        st.rerun()
