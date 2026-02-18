import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import time
import textwrap
import numpy as np # 작업일 계산을 위해 추가

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 디자인 CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="디자인1본부 일정관리", layout="wide")

# CSS: 화면 및 인쇄 스타일링
custom_css = """
<style>
    /* 메인 타이틀 & 서브헤더 */
    .title-text { font-size: 1.8rem !important; font-weight: 700; color: #31333F; margin-bottom: 10px; }
    .subheader-text { font-size: 1.2rem !important; font-weight: 600; color: #31333F; padding-top: 5px; }
    
    /* 입력 폼 스타일 */
    div[data-testid="stForm"] .stSelectbox { margin-bottom: -15px !important; }
    div[data-testid="stForm"] .stTextInput { margin-top: 0px !important; }
    .sort-label { font-size: 14px; font-weight: 600; display: flex; align-items: center; justify-content: flex-end; height: 40px; padding-right: 10px; }

    /* [중요] 인쇄 모드 스타일 */
    @media print {
        header, footer, aside, 
        [data-testid="stSidebar"], [data-testid="stToolbar"], 
        .stButton, .stDownloadButton, .stExpander, .stForm, 
        div[data-testid="stVerticalBlockBorderWrapper"], button,
        .no-print, .sort-area, .stSelectbox, .stCheckbox, .stToggle
        { display: none !important; }

        body, .stApp { 
            background-color: white !important; 
            color: black !important;
            zoom: 80%; /* 인쇄 시 축소 */
        }
        
        .main .block-container { 
            max-width: 100% !important; width: 100% !important; padding: 10px !important; margin: 0 !important; 
        }

        /* 차트 및 표 설정 */
        div[data-testid="stDataEditor"], .js-plotly-plot { 
            break-inside: avoid !important; 
            margin-bottom: 20px !important; 
            width: 100% !important; 
        }

        /* 표 인쇄 스타일 강제 적용 */
        div[data-testid="stDataEditor"] table {
            color: black !important;
            font-size: 10px !important;
            border: 1px solid #000 !important;
            border-collapse: collapse !important;
        }
        /* 헤더: 검은색 20% (회색) */
        div[data-testid="stDataEditor"] th {
            background-color: #cccccc !important; 
            color: black !important;
            border: 1px solid black !important;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }
        /* 내용: 흰 바탕 검은 글씨 */
        div[data-testid="stDataEditor"] td {
            background-color: white !important;
            color: black !important;
            border: 1px solid #ddd !important;
        }
        
        @page { size: landscape; margin: 0.5cm; }
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

st.markdown('<div class="title-text">📅 디자인1본부 1팀 일정</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. 유틸리티 함수 (작업일 계산 등)
# -----------------------------------------------------------------------------
def get_business_days(start_date, end_date):
    """시작일과 종료일 사이의 평일(주말 제외) 수 계산 (inclusive)"""
    if pd.isna(start_date) or pd.isna(end_date): return 0
    s = pd.to_datetime(start_date).date()
    e = pd.to_datetime(end_date).date()
    if s > e: return 0
    # busday_count는 종료일 미포함이므로 +1일 처리하여 계산
    return np.busday_count(s, e + timedelta(days=1))

def add_business_days(start_date, days):
    """시작일에 평일 n일을 더한 날짜 반환"""
    if pd.isna(start_date) or days <= 0: return start_date
    s = pd.to_datetime(start_date).date()
    # 1일 작업이면 당일 종료 (days-1)
    target_date = np.busday_offset(s, int(days) - 1, roll='forward')
    return pd.to_datetime(target_date)

# -----------------------------------------------------------------------------
# 3. 데이터 로드 및 전처리
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def load_data_from_sheet():
    try:
        df = conn.read(worksheet="Sheet1")
        return df
    except Exception as e:
        st.error(f"구글 시트 연결 오류: {e}")
        return pd.DataFrame()

def process_dataframe(df):
    required_cols = ["프로젝트명", "구분", "담당자", "Activity", "작업기간", "시작일", "종료일", "진행률"]
    
    if df.empty:
        df = pd.DataFrame(columns=required_cols)
    else:
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""

    df["시작일"] = pd.to_datetime(df["시작일"], errors='coerce')
    df["종료일"] = pd.to_datetime(df["종료일"], errors='coerce')
    
    today = pd.to_datetime(datetime.today().strftime("%Y-%m-%d"))
    df["남은기간"] = (df["종료일"] - today).dt.days.fillna(0).astype(int)

    if "진행률" in df.columns and df["진행률"].dtype == 'object':
        df["진행률"] = df["진행률"].astype(str).str.replace('%', '')
    df["진행률"] = pd.to_numeric(df["진행률"], errors='coerce').fillna(0).astype(int)
    
    # 작업기간(평일) 자동 계산 (데이터 무결성 유지)
    # 기존에 값이 없거나 0이면 날짜 기준으로 계산
    df["작업기간"] = df.apply(
        lambda x: get_business_days(x["시작일"], x["종료일"]) if pd.notna(x["시작일"]) and pd.notna(x["종료일"]) else 0, 
        axis=1
    )
    
    df["진행상황"] = df["진행률"]
    
    if "_original_id" not in df.columns:
        df["_original_id"] = range(len(df))
    else:
        df["_original_id"] = df["_original_id"].fillna(pd.Series(range(len(df))))
        
    return df

if 'data' not in st.session_state:
    raw_data = load_data_from_sheet()
    st.session_state['data'] = process_dataframe(raw_data)
    # 초기 세션 설정
    if 'show_completed' not in st.session_state: st.session_state['show_completed'] = False

data = st.session_state['data'].copy()
today = pd.to_datetime(datetime.today().strftime("%Y-%m-%d"))

# 드롭다운 리스트
def get_unique_list(df, col_name):
    return sorted(df[col_name].astype(str).dropna().unique().tolist()) if col_name in df.columns else []

projects_list = get_unique_list(data, "프로젝트명")
items_list = get_unique_list(data, "구분")
members_list = get_unique_list(data, "담당자")
activity_list = get_unique_list(data, "Activity")

def wrap_labels(text, width=15):
    if pd.isna(text) or text == "": return ""
    return "<br>".join(textwrap.wrap(str(text), width=width, break_long_words=True))

# -----------------------------------------------------------------------------
# 4. [시각화] 테이블형 간트차트
# -----------------------------------------------------------------------------
if st.session_state['show_completed']:
    chart_base_data = data.copy()
else:
    chart_base_data = data[data["진행률"] < 100].copy()

chart_data = chart_base_data.dropna(subset=["시작일", "종료일"]).copy()

if not chart_data.empty:
    chart_data["프로젝트명_표시"] = chart_data["프로젝트명"].apply(lambda x: wrap_labels(x, 12))
    chart_data["Activity_표시"] = chart_data["Activity"].apply(lambda x: wrap_labels(x, 12))
    chart_data = chart_data.sort_values(by=["시작일"], ascending=False).reset_index(drop=True)
    
    unique_members = chart_data["담당자"].unique()
    colors = px.colors.qualitative.Pastel
    color_map = {member: colors[i % len(colors)] for i, member in enumerate(unique_members)}
    
    fig = make_subplots(
        rows=1, cols=5,
        shared_yaxes=True,
        horizontal_spacing=0.005, 
        column_widths=[0.15, 0.08, 0.08, 0.12, 0.57], 
        subplot_titles=("<b>프로젝트명</b>", "<b>구분</b>", "<b>담당자</b>", "<b>Activity</b>", ""),
        specs=[[{"type": "scatter"}, {"type": "scatter"}, {"type": "scatter"}, {"type": "scatter"}, {"type": "xy"}]]
    )

    num_rows = len(chart_data)
    y_axis = list(range(num_rows))
    common_props = dict(mode="text", textposition="middle center", textfont=dict(color="black", size=11), hoverinfo="skip")

    fig.add_trace(go.Scatter(x=[0.5]*num_rows, y=y_axis, text=chart_data["프로젝트명_표시"], **common_props), row=1, col=1)
    fig.add_trace(go.Scatter(x=[0.5]*num_rows, y=y_axis, text=chart_data["구분"], **common_props), row=1, col=2)
    fig.add_trace(go.Scatter(x=[0.5]*num_rows, y=y_axis, text=chart_data["담당자"], **common_props), row=1, col=3)
    fig.add_trace(go.Scatter(x=[0.5]*num_rows, y=y_axis, text=chart_data["Activity_표시"], **common_props), row=1, col=4)

    # 간트 바 차트
    for idx, row in chart_data.iterrows():
        start_ms = row["시작일"].timestamp() * 1000
        end_ms = row["종료일"].timestamp() * 1000
        duration_ms = end_ms - start_ms
        
        # [수정] Bar 텍스트: 휴일 제외 작업일수 사용
        work_days = get_business_days(row["시작일"], row["종료일"])
        bar_text = f"{work_days}일 / {row['진행률']}%"

        fig.add_trace(go.Bar(
            base=[start_ms], x=[duration_ms], y=[idx],
            orientation='h',
            marker_color=color_map.get(row["담당자"], "grey"),
            opacity=0.8,
            hoverinfo="text",
            hovertext=f"<b>{row['프로젝트명']}</b><br>{row['Activity']}<br>{row['시작일'].strftime('%Y-%m-%d')} ~ {row['종료일'].strftime('%Y-%m-%d')}<br>작업일: {work_days}일",
            text=bar_text, textposition='inside', insidetextanchor='middle',
            textfont=dict(color='black', size=10),
            showlegend=False
        ), row=1, col=5)

    view_start = today - timedelta(days=5)
    view_end = today + timedelta(days=20)
    
    for i in range(1, 5):
        fig.update_xaxes(showgrid=False, zeroline=False, showticklabels=False, row=1, col=i)
        fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=False, row=1, col=i)

    # [수정] 날짜 형식 변경 (Feb 18 \n (Wed))
    fig.update_xaxes(
        type="date", range=[view_start, view_end], side="top",
        tickfont=dict(size=10, color="black"),
        gridcolor='rgba(0,0,0,0.1)', 
        dtick="D1", 
        tickformat="%b %d\n(%a)", # 월 일 (줄바꿈) 요일
        row=1, col=5
    )
    fig.update_yaxes(showticklabels=False, showgrid=False, fixedrange=True, row=1, col=5)
    fig.add_vline(x=today.timestamp() * 1000, line_width=1.5, line_dash="dot", line_color="red", row=1, col=5)

    shapes = [dict(type="line", xref="paper", yref="y", x0=0, x1=1, y0=i-0.5, y1=i-0.5, line=dict(color="rgba(0,0,0,0.1)", width=1)) for i in range(num_rows + 1)]
    
    # [수정] 제목 패딩 추가 (간격 15 확보)
    fig.update_layout(
        height=max(300, num_rows * 40 + 80),
        margin=dict(l=10, r=10, t=60, b=10), # Top margin increased
        title={
            'text': "Project Schedule",
            'y': 0.95, 'x': 0.35, 'xanchor': 'left', 'yanchor': 'top',
            'pad': dict(b=15) # Title padding
        },
        paper_bgcolor='white', plot_bgcolor='white',
        showlegend=False, shapes=shapes, dragmode="pan"
    )
    
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': False})
else:
    st.info("📅 표시할 일정이 없습니다.")

# -----------------------------------------------------------------------------
# 5. [입력 섹션] 상호 연산 시스템 적용
# -----------------------------------------------------------------------------
st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# 입력값 상태 관리 (상호 연산을 위해)
if 'new_start' not in st.session_state: st.session_state.new_start = datetime.today()
if 'new_end' not in st.session_state: st.session_state.new_end = datetime.today()
if 'new_days' not in st.session_state: st.session_state.new_days = 1

# 콜백 함수: 날짜/기간 변경 시 상호 계산
def on_date_change():
    # 시작일, 종료일 변경 -> 기간 재계산
    s = st.session_state.new_start
    e = st.session_state.new_end
    if s and e:
        st.session_state.new_days = get_business_days(s, e)

def on_days_change():
    # 기간 변경 -> 종료일 재계산 (시작일 고정)
    s = st.session_state.new_start
    d = st.session_state.new_days
    if s and d > 0:
        st.session_state.new_end = add_business_days(s, d)

with st.expander("➕ 새 일정 등록하기 (기간 자동 계산)"):
    # 폼 대신 직접 입력 위젯 사용 (실시간 연동을 위해)
    c1, c2 = st.columns(2)
    c3, c4, c5 = st.columns([1, 1, 1])

    with c1:
        new_proj = st.selectbox("1. 프로젝트명", ["선택하세요"] + projects_list + ["➕ 직접 입력"])
        if new_proj == "➕ 직접 입력": new_proj = st.text_input("└ 프로젝트명 입력")
        new_item = st.selectbox("2. 구분", ["선택하세요"] + items_list + ["➕ 직접 입력"])
        if new_item == "➕ 직접 입력": new_item = st.text_input("└ 구분 입력")

    with c2:
        new_member = st.selectbox("3. 담당자", ["선택하세요"] + members_list + ["➕ 직접 입력"])
        if new_member == "➕ 직접 입력": new_member = st.text_input("└ 담당자 입력")
        new_act = st.selectbox("4. Activity", ["선택하세요"] + activity_list + ["➕ 직접 입력"])
        if new_act == "➕ 직접 입력": new_act = st.text_input("└ Activity 입력")

    with c3:
        # 5. 시작일
        st.date_input("5. 시작일", key="new_start", on_change=on_date_change)
    with c4:
        # [추가] 6. 작업기간 (상호 연산)
        st.number_input("6. 작업기간(일)", min_value=1, value=1, key="new_days", on_change=on_days_change)
    with c5:
        # 7. 종료일
        st.date_input("7. 종료일", key="new_end", on_change=on_date_change)

    if st.button("저장", type="primary", use_container_width=True):
        if not new_proj or new_proj == "선택하세요":
            st.error("프로젝트명을 입력해주세요.")
        else:
            new_row = pd.DataFrame([{
                "프로젝트명": new_proj, "구분": new_item if new_item != "선택하세요" else "", 
                "담당자": new_member if new_member != "선택하세요" else "",
                "Activity": new_act if new_act != "선택하세요" else "", 
                "시작일": pd.to_datetime(st.session_state.new_start), 
                "종료일": pd.to_datetime(st.session_state.new_end), 
                "작업기간": st.session_state.new_days,
                "진행률": 0,
                "_original_id": len(st.session_state['data']) + 9999
            }])
            st.session_state['data'] = pd.concat([st.session_state['data'], new_row], ignore_index=True)
            
            try:
                save_data = st.session_state['data'].copy()
                if "_original_id" in save_data.columns: save_data.drop(columns=["_original_id"], inplace=True)
                save_data["시작일"] = save_data["시작일"].dt.strftime("%Y-%m-%d").replace("NaT", "")
                save_data["종료일"] = save_data["종료일"].dt.strftime("%Y-%m-%d").replace("NaT", "")
                
                conn.update(worksheet="Sheet1", data=save_data)
                load_data_from_sheet.clear()
                st.success("✅ 추가되었습니다!")
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"저장 실패: {e}")

# -----------------------------------------------------------------------------
# 6. 데이터 에디터 및 저장
# -----------------------------------------------------------------------------
st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
c_title, c_label, c_box, c_sort, c_show = st.columns([0.22, 0.08, 0.17, 0.15, 0.38])

with c_title: st.markdown('<div class="subheader-text no-print">📝 업무 리스트</div>', unsafe_allow_html=True)
with c_label: st.markdown('<div class="sort-label no-print">정렬 기준</div>', unsafe_allow_html=True)
with c_box: sort_col = st.selectbox("정렬", ["프로젝트명", "구분", "담당자", "시작일", "종료일"], label_visibility="collapsed")
with c_sort: sort_asc = st.toggle("오름차순", value=True)
with c_show: 
    show_completed = st.toggle("완료된 업무 보기", value=st.session_state['show_completed'])
    if show_completed != st.session_state['show_completed']:
        st.session_state['show_completed'] = show_completed
        st.rerun()

editor_df = st.session_state['data'].copy()
if not st.session_state['show_completed']: editor_df = editor_df[editor_df["진행률"] < 100]
editor_df = editor_df.sort_values(by=sort_col, ascending=sort_asc)

# [수정] Activity 우측에 작업기간 추가
display_cols = ["프로젝트명", "구분", "담당자", "Activity", "작업기간", "시작일", "종료일", "남은기간", "진행률", "진행상황", "_original_id"]

edited_df = st.data_editor(
    editor_df,
    height=(len(editor_df) + 1) * 35 + 3,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "_original_id": None,
        "프로젝트명": st.column_config.SelectboxColumn("프로젝트명", options=projects_list, required=True),
        "구분": st.column_config.SelectboxColumn("구분", options=items_list),
        "담당자": st.column_config.SelectboxColumn("담당자", options=members_list),
        "Activity": st.column_config.SelectboxColumn("Activity", options=activity_list),
        "작업기간": st.column_config.NumberColumn("작업기간(일)", min_value=1, format="%d"),
        "진행률": st.column_config.NumberColumn("진행률(%)", min_value=0, max_value=100, step=10, format="%d"),
        "진행상황": st.column_config.ProgressColumn("Bar", format="%d%%", min_value=0, max_value=100),
        "시작일": st.column_config.DateColumn("시작일", format="YYYY-MM-DD"),
        "종료일": st.column_config.DateColumn("종료일", format="YYYY-MM-DD"),
        "남은기간": st.column_config.NumberColumn("D-Day", format="%d일", disabled=True),
    },
    column_order=[c for c in display_cols if c != "_original_id"],
    hide_index=True,
    key="data_editor"
)

if st.button("💾 변경사항 저장하기", type="primary", use_container_width=True):
    try:
        with st.spinner("저장 중..."):
            master_df = st.session_state['data'].copy()
            if "_original_id" in master_df.columns:
                master_df.set_index("_original_id", inplace=True)
                updates = edited_df.dropna(subset=["_original_id"]).set_index("_original_id")
                
                # [로직] 에디터에서 '작업기간'만 수정한 경우 종료일 업데이트
                # 변경된 행을 감지하여 기간 재계산
                common_ids = updates.index.intersection(master_df.index)
                for idx in common_ids:
                    old_row = master_df.loc[idx]
                    new_row = updates.loc[idx]
                    
                    # 작업기간이 변경되었고 날짜는 그대로인 경우 -> 종료일 업데이트
                    if new_row["작업기간"] != old_row["작업기간"]:
                        new_end_date = add_business_days(new_row["시작일"], new_row["작업기간"])
                        updates.at[idx, "종료일"] = new_end_date
                    # 종료일이나 시작일이 변경된 경우 -> 작업기간 업데이트
                    elif (new_row["시작일"] != old_row["시작일"]) or (new_row["종료일"] != old_row["종료일"]):
                        updates.at[idx, "작업기간"] = get_business_days(new_row["시작일"], new_row["종료일"])

                master_df.update(updates)
                master_df.reset_index(inplace=True)
                
                # 새 행 추가
                new_rows = edited_df[edited_df["_original_id"].isna() | (edited_df["_original_id"] == "")]
                if not new_rows.empty:
                    new_rows = new_rows.drop(columns=["_original_id"], errors='ignore')
                    # 새 행도 기간 계산
                    new_rows["작업기간"] = new_rows.apply(lambda x: get_business_days(x["시작일"], x["종료일"]), axis=1)
                    master_df = pd.concat([master_df, new_rows], ignore_index=True)

                save_df = master_df.copy()
                if "_original_id" in save_df.columns: save_df.drop(columns=["_original_id"], inplace=True)
                
                save_df["시작일"] = pd.to_datetime(save_df["시작일"]).dt.strftime("%Y-%m-%d").replace("NaT", "")
                save_df["종료일"] = pd.to_datetime(save_df["종료일"]).dt.strftime("%Y-%m-%d").replace("NaT", "")
                
                conn.update(worksheet="Sheet1", data=save_df)
                load_data_from_sheet.clear()
                st.session_state['data'] = process_dataframe(save_df)
                st.success("✅ 저장되었습니다.")
                time.sleep(1)
                st.rerun()
    except Exception as e:
        st.error(f"오류: {e}")
