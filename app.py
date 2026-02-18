import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta, date
import time
import textwrap
import numpy as np
import pytz

# 휴일 계산 라이브러리
try:
    import holidays
    kr_holidays = holidays.KR()
except ImportError:
    kr_holidays = {}

# [중요] 한국 시간(KST) 설정
KST = pytz.timezone('Asia/Seoul')

def get_now_kst():
    """현재 한국 시간을 구하되, 타임존 정보를 제거하여 반환 (Naive Datetime)"""
    return datetime.now(KST).replace(tzinfo=None)

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 디자인 CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="디자인1본부 1팀 일정", layout="wide")

custom_css = """
<style>
    /* 메인 타이틀 */
    .title-text { font-size: 1.8rem !important; font-weight: 700; color: #333333 !important; margin-bottom: 10px; }
    
    /* 입력 폼 */
    div[data-testid="stForm"] .stSelectbox { margin-bottom: -15px !important; }
    div[data-testid="stForm"] .stTextInput { margin-top: 0px !important; }
    .sort-label { font-size: 14px; font-weight: 600; display: flex; align-items: center; justify-content: flex-end; height: 40px; padding-right: 10px; }

    /* 업무리스트 테이블 헤더 */
    div[data-testid="stDataEditor"] th {
        background-color: #cccccc !important; 
        color: black !important;
        font-size: 14px !important;
        font-weight: 700 !important;
        border: 1px solid black !important;
    }
    div[data-testid="stDataEditor"] td { font-size: 12px !important; }

    /* 인쇄 모드 스타일 */
    @media print {
        header, footer, aside, [data-testid="stSidebar"], [data-testid="stToolbar"], 
        .stButton, .stDownloadButton, .stExpander, .stForm, 
        div[data-testid="stVerticalBlockBorderWrapper"], button,
        .no-print, .sort-area, .stSelectbox, .stCheckbox, .stToggle
        { display: none !important; }

        body, .stApp { background-color: white !important; color: rgba(0, 0, 0, 0.8) !important; zoom: 80%; }
        .main .block-container { max-width: 100% !important; width: 100% !important; padding: 10px !important; margin: 0 !important; }
        
        div[data-testid="stDataEditor"], .js-plotly-plot { break-inside: avoid !important; margin-bottom: 20px !important; width: 100% !important; }
        div[data-testid="stDataEditor"] table { color: rgba(0, 0, 0, 0.8) !important; background-color: white !important; border: 1px solid #000 !important; border-collapse: collapse !important; width: 100% !important; }
        div[data-testid="stDataEditor"] th { background-color: #cccccc !important; color: black !important; font-size: 14px !important; font-weight: bold !important; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        div[data-testid="stDataEditor"] td { background-color: white !important; color: rgba(0, 0, 0, 0.8) !important; border: 1px solid #ddd !important; }
        @page { size: landscape; margin: 0.5cm; }
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

st.markdown('<div class="title-text">📅 디자인1본부 1팀 일정</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. 유틸리티 함수 (Numpy 최적화)
# -----------------------------------------------------------------------------
def is_holiday(date_obj):
    if date_obj.weekday() >= 5: return True
    if date_obj.strftime("%Y-%m-%d") in kr_holidays: return True
    return False

def get_business_days(start_date, end_date):
    if pd.isna(start_date) or pd.isna(end_date): return 0
    s = np.datetime64(start_date, 'D')
    e = np.datetime64(end_date, 'D')
    if s > e: return 0
    holidays_list = list(kr_holidays.keys()) if kr_holidays else []
    count = np.busday_count(s, e + 1, weekmask='1111100', holidays=holidays_list)
    return int(count)

def add_business_days(start_date, days):
    if pd.isna(start_date) or days <= 0: return start_date
    s = np.datetime64(start_date, 'D')
    holidays_list = list(kr_holidays.keys()) if kr_holidays else []
    try:
        target = np.busday_offset(s, int(days) - 1, roll='forward', weekmask='1111100', holidays=holidays_list)
        return pd.to_datetime(target).date()
    except:
        return start_date

# -----------------------------------------------------------------------------
# 3. 데이터 로드 및 전처리
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def load_data_from_sheet():
    try:
        return conn.read(worksheet="Sheet1")
    except Exception as e:
        st.error(f"구글 시트 연결 오류: {e}")
        return pd.DataFrame()

def process_dataframe(df):
    required_cols = ["프로젝트명", "구분", "담당자", "Activity", "작업기간", "시작일", "종료일", "진행률"]
    if df.empty:
        df = pd.DataFrame(columns=required_cols)
    else:
        for col in required_cols:
            if col not in df.columns: df[col] = ""

    df["시작일"] = pd.to_datetime(df["시작일"], errors='coerce')
    df["종료일"] = pd.to_datetime(df["종료일"], errors='coerce')
    
    now_kst = get_now_kst()
    today_naive = pd.to_datetime(now_kst.date())
    
    df["남은기간"] = (df["종료일"] - today_naive).dt.days.fillna(0).astype(int)

    if "진행률" in df.columns and df["진행률"].dtype == 'object':
        df["진행률"] = df["진행률"].astype(str).str.replace('%', '')
    df["진행률"] = pd.to_numeric(df["진행률"], errors='coerce').fillna(0).astype(int)
    
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
    if 'show_completed' not in st.session_state: st.session_state['show_completed'] = False

data = st.session_state['data'].copy()
now_kst = get_now_kst()
today = pd.to_datetime(now_kst.date())

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

with st.sidebar:
    st.markdown("### 🎨 보기 설정")
    force_print_theme = st.checkbox("🖨️ 인쇄용 테마 (배경 흰색)", value=False)
    is_dark_mode = st.checkbox("🌙 다크 모드 최적화 (배경 어두움)", value=False)

if not chart_data.empty:
    chart_data = chart_data.sort_values(by=["프로젝트명", "시작일"], ascending=[True, True]).reset_index(drop=True)
    
    proj_display_list = []
    prev_proj = None
    for proj in chart_data["프로젝트명"]:
        if proj == prev_proj: proj_display_list.append("") 
        else: proj_display_list.append(proj); prev_proj = proj
    
    chart_data["프로젝트명_표시"] = [wrap_labels(p, 12) for p in proj_display_list]
    chart_data["Activity_표시"] = chart_data["Activity"].apply(lambda x: wrap_labels(x, 12))
    
    unique_members = chart_data["담당자"].unique()
    colors = px.colors.qualitative.Pastel
    color_map = {member: colors[i % len(colors)] for i, member in enumerate(unique_members)}
    
    fig = make_subplots(
        rows=1, cols=5,
        shared_yaxes=True,
        horizontal_spacing=0.005, 
        column_widths=[0.10, 0.05, 0.05, 0.10, 0.70], 
        subplot_titles=(
            "<span style='font-size:14px; color:black; font-weight:bold'>프로젝트명</span>", 
            "<span style='font-size:14px; color:black; font-weight:bold'>구분</span>", 
            "<span style='font-size:14px; color:black; font-weight:bold'>담당자</span>", 
            "<span style='font-size:14px; color:black; font-weight:bold'>Activity</span>", 
            ""
        ),
        specs=[[{"type": "scatter"}, {"type": "scatter"}, {"type": "scatter"}, {"type": "scatter"}, {"type": "xy"}]]
    )

    num_rows = len(chart_data)
    y_axis = list(range(num_rows))
    
    if force_print_theme:
        text_color = "black"
    elif is_dark_mode:
        text_color = "white"
    else:
        text_color = None

    common_props = dict(mode="text", textposition="middle center", textfont=dict(color=text_color, size=11), hoverinfo="skip")

    fig.add_trace(go.Scatter(x=[0.5]*num_rows, y=y_axis, text=chart_data["프로젝트명_표시"], **common_props), row=1, col=1)
    fig.add_trace(go.Scatter(x=[0.5]*num_rows, y=y_axis, text=chart_data["구분"], **common_props), row=1, col=2)
    fig.add_trace(go.Scatter(x=[0.5]*num_rows, y=y_axis, text=chart_data["담당자"], **common_props), row=1, col=3)
    fig.add_trace(go.Scatter(x=[0.5]*num_rows, y=y_axis, text=chart_data["Activity_표시"], **common_props), row=1, col=4)

    for idx, row in chart_data.iterrows():
        start_date = row["시작일"]
        end_date = row["종료일"]
        
        # 종료일 포함하여 1일 추가 계산
        duration_ms = ((end_date - start_date).days + 1) * 24 * 3600 * 1000
        work_days = get_business_days(row["시작일"], row["종료일"])
        bar_text = f"{work_days}일 / {row['진행률']}%"

        fig.add_trace(go.Bar(
            base=[start_date], 
            x=[duration_ms], 
            y=[idx],
            orientation='h',
            marker_color=color_map.get(row["담당자"], "grey"),
            opacity=0.8,
            hoverinfo="text",
            hovertext=f"<b>{row['프로젝트명']}</b><br>{row['Activity']}<br>{row['시작일'].strftime('%Y-%m-%d')} ~ {row['종료일'].strftime('%Y-%m-%d')}<br>작업일: {work_days}일",
            text=bar_text, textposition='inside', insidetextanchor='middle',
            textfont=dict(color='black', size=10),
            showlegend=False
        ), row=1, col=5)

    # -------------------------------------------------------------------------
    # 렌더링 범위 제한
    # -------------------------------------------------------------------------
    view_start_initial = today - timedelta(days=5)
    view_end_initial = today + timedelta(days=20)

    # 루프는 휴일 계산을 위해서만 최소한으로 돕니다.
    calc_start = today - timedelta(days=180)
    calc_end = today + timedelta(days=180)
    
    if not chart_data.empty:
        min_date = chart_data["시작일"].min()
        max_date = chart_data["종료일"].max()
        if pd.notna(min_date) and pd.notna(max_date):
            safe_min = today - timedelta(days=365)
            safe_max = today + timedelta(days=365)
            calc_start = max(min(calc_start, min_date - timedelta(days=30)), safe_min)
            calc_end = min(max(calc_end, max_date + timedelta(days=30)), safe_max)

    if is_dark_mode and not force_print_theme:
        holiday_fill_color = "rgba(255, 255, 255, 0.15)"
        holiday_text_color = "rgba(255, 255, 255, 0.4)"
    else:
        holiday_fill_color = "rgba(0, 0, 0, 0.15)"
        holiday_text_color = "rgba(0, 0, 0, 0.4)"

    # 1. 가로선 (Row 구분)
    for i in range(num_rows + 1):
        fig.add_shape(type="line", xref="paper", yref="y", x0=0, x1=1, y0=i-0.5, y1=i-0.5, line=dict(color="rgba(128,128,128,0.2)", width=1))

    tick_vals = []
    tick_text = []
    day_map = {'Mon': '월', 'Tue': '화', 'Wed': '수', 'Thu': '목', 'Fri': '금', 'Sat': '토', 'Sun': '일'}
    
    # 2. 휴일 배경 및 날짜 라벨 루프
    # [최적화] 매일 세로선을 긋지 않습니다. (세로선은 Native Grid로 대체)
    max_loops = 2000
    loop_count = 0
    curr_check = calc_start
    
    while curr_check <= calc_end and loop_count < max_loops:
        tick_vals.append(curr_check + timedelta(hours=12)) # 12시간 오프셋 (중앙 정렬)
        korean_day = day_map[curr_check.strftime('%a')]
        formatted_date = f"{curr_check.month}/{curr_check.day} / {korean_day}"
        
        is_hol = is_holiday(curr_check)
        if is_hol:
            formatted_date = f"<span style='color:{holiday_text_color}'>{formatted_date}</span>" 
            # 휴일 배경만 그립니다.
            fig.add_shape(
                type="rect",
                xref="x", yref="y", 
                x0=curr_check, 
                x1=curr_check + timedelta(days=1),
                y0=-0.5, 
                y1=num_rows - 0.5,
                fillcolor=holiday_fill_color,
                opacity=1,
                layer="below", 
                line_width=0,
                row=1, col=5 
            )

        tick_text.append(formatted_date)
        curr_check += timedelta(days=1)
        loop_count += 1

    # 축 설정
    for i in range(1, 5):
        fig.update_xaxes(showgrid=False, zeroline=False, showticklabels=False, row=1, col=i)
        fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=False, autorange="reversed", row=1, col=i)

    # [핵심] Native Grid 사용으로 성능 향상 및 세로선 구현
    fig.update_xaxes(
        type="date", 
        range=[view_start_initial, view_end_initial], 
        side="top",
        tickfont=dict(size=10, color=text_color),
        tickvals=tick_vals,
        ticktext=tick_text,
        # Native Grid 켜기
        showgrid=True,
        gridcolor='rgba(128,128,128,0.2)',
        griddash='dash',
        dtick="D1",
        ticklabelmode="period", # 라벨은 중앙에, 그리드는 경계선에
        row=1, col=5
    )
    fig.update_yaxes(showticklabels=False, showgrid=False, fixedrange=True, autorange="reversed", row=1, col=5)
    
    fig.add_vline(x=now_kst, line_width=1.5, line_dash="dot", line_color="red", row=1, col=5)

    layout_bg = "white" if force_print_theme else None
    
    fig.update_layout(
        height=max(300, num_rows * 40 + 80),
        margin=dict(l=10, r=10, t=60, b=10), 
        title={
            'text': "<b>Project Schedule</b>",
            'y': 0.98, 'x': 0.35, 'xanchor': 'left', 'yanchor': 'top', 
            'pad': dict(b=5),
            'font': dict(color=text_color, size=16)
        },
        font=dict(color=text_color),
        paper_bgcolor=layout_bg, 
        plot_bgcolor=layout_bg,
        showlegend=False, 
        dragmode="pan"
    )
    
    if force_print_theme:
        for annotation in fig['layout']['annotations']:
            annotation['font']['color'] = "black"

    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': True}, theme="streamlit")
else:
    st.info("📅 표시할 일정이 없습니다.")

# -----------------------------------------------------------------------------
# 5. [입력 섹션]
# -----------------------------------------------------------------------------
st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

if 'new_start' not in st.session_state: st.session_state.new_start = get_now_kst().date()
if 'new_end' not in st.session_state: st.session_state.new_end = get_now_kst().date()
if 'new_days' not in st.session_state: st.session_state.new_days = 1

def on_date_change():
    s, e = st.session_state.new_start, st.session_state.new_end
    if s and e: st.session_state.new_days = get_business_days(s, e)

def on_days_change():
    s, d = st.session_state.new_start, st.session_state.new_days
    if s and d > 0: st.session_state.new_end = add_business_days(s, d)

with st.expander("➕ 새 일정 등록하기 (기간 자동 계산)"):
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
    with c3: st.date_input("5. 시작일", key="new_start", on_change=on_date_change)
    with c4: st.number_input("6. 작업기간(일)", min_value=1, value=1, key="new_days", on_change=on_days_change)
    with c5: st.date_input("7. 종료일", key="new_end", on_change=on_date_change)

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
                # [수정] 변수명 오타 수정 save_df -> save_data
                save_data = st.session_state['data'].copy()
                if "_original_id" in save_data.columns: save_data.drop(columns=["_original_id"], inplace=True)
                save_data["시작일"] = save_data["시작일"].dt.strftime("%Y-%m-%d").replace("NaT", "")
                save_data["종료일"] = save_data["종료일"].dt.strftime("%Y-%m-%d").replace("NaT", "")
                conn.update(worksheet="Sheet1", data=save_data)
                
                # [수정] process_dataframe 인자도 save_data로 수정
                load_data_from_sheet.clear()
                st.session_state['data'] = process_dataframe(save_data)
                st.success("✅ 추가되었습니다!")
                time.sleep(0.5)
                st.rerun()
            except Exception as e: st.error(f"저장 실패: {e}")

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
                
                common_ids = updates.index.intersection(master_df.index)
                for idx in common_ids:
                    old_row = master_df.loc[idx]
                    new_row = updates.loc[idx]
                    if new_row["작업기간"] != old_row["작업기간"]:
                        new_end_date = add_business_days(new_row["시작일"], new_row["작업기간"])
                        updates.at[idx, "종료일"] = new_end_date
                    elif (new_row["시작일"] != old_row["시작일"]) or (new_row["종료일"] != old_row["종료일"]):
                        updates.at[idx, "작업기간"] = get_business_days(new_row["시작일"], new_row["종료일"])

                master_df.update(updates)
                master_df.reset_index(inplace=True)
                
                new_rows = edited_df[edited_df["_original_id"].isna() | (edited_df["_original_id"] == "")]
                if not new_rows.empty:
                    new_rows = new_rows.drop(columns=["_original_id"], errors='ignore')
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
    except Exception as e: st.error(f"오류: {e}")
