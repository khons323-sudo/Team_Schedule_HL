import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import time
import textwrap 

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 디자인 CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="디자인1본부 일정관리", layout="wide")

# CSS: 화면 및 인쇄 스타일링
custom_css = """
<style>
    /* 1. 메인 타이틀 & 서브헤더 스타일 */
    .title-text, .subheader-text {
        font-size: 1.3rem !important;
        font-weight: 700;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.5;
        color: rgb(49, 51, 63);
    }
    
    /* 상단 여백 최소화 (삭제 요청 복구됨 - 기본값) */

    /* 입력 폼 스타일링 */
    div[data-testid="stForm"] .stSelectbox { margin-bottom: -15px !important; }
    div[data-testid="stForm"] .stTextInput { margin-top: 0px !important; }
    
    /* 정렬 컨트롤 라벨 스타일 */
    .sort-label {
        font-size: 14px;
        font-weight: 600;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        height: 40px;
        padding-right: 10px;
    }
    
    div[data-testid="stSelectbox"] { margin-top: 2px; }
    div[data-testid="stCheckbox"] { margin-top: 8px; }
    div[data-testid="stCheckbox"] label { font-size: 14px !important; }
    
    /* [중요] 인쇄 모드 스타일 */
    @media print {
        header, footer, aside, 
        [data-testid="stSidebar"], [data-testid="stToolbar"], 
        .stButton, .stDownloadButton, .stExpander, .stForm, 
        div[data-testid="stVerticalBlockBorderWrapper"], button,
        .no-print, .sort-area, .stSelectbox, .stCheckbox
        { display: none !important; }

        body, .stApp { 
            background-color: white !important; 
            color: black !important;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
            zoom: 75%; 
        }
        * { text-shadow: none !important; }

        .main .block-container { 
            max-width: 100% !important; 
            width: 100% !important; 
            padding: 0 !important; 
            margin: 0 !important; 
        }
        
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] { 
            height: auto !important; 
            width: 100% !important;
            overflow: visible !important; 
            display: block !important; 
            position: static !important;
        }

        /* 차트 및 표 설정 */
        div[data-testid="stDataEditor"], .js-plotly-plot { 
            break-inside: avoid !important; 
            margin-bottom: 20px !important; 
            width: 100% !important; 
        }
        
        /* 표 헤더/내용 스타일 */
        div[data-testid="stDataEditor"] table { font-size: 10px !important; border: 1px solid #000 !important; width: 100% !important; color: black !important; }
        div[data-testid="stDataEditor"] th { background-color: #cccccc !important; color: black !important; border-bottom: 2px solid black !important; }
        div[data-testid="stDataEditor"] td { background-color: white !important; color: black !important; border-bottom: 1px solid #ddd !important; }

        @page { size: portrait; margin: 0.5cm; }
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# 메인 타이틀
st.markdown('<div class="title-text">📅 디자인1본부 1팀 일정</div>', unsafe_allow_html=True)

# 세션 상태 초기화
if 'show_completed' not in st.session_state:
    st.session_state['show_completed'] = False

# -----------------------------------------------------------------------------
# 2. 데이터 로드 및 캐싱
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=3600)
def load_data_from_sheet():
    return conn.read(worksheet="Sheet1")

def process_dataframe(df):
    required_cols = ["프로젝트명", "구분", "담당자", "Activity", "시작일", "종료일", "진행률"]
    if df.empty:
        for col in required_cols:
            df[col] = ""
        df["진행률"] = 0
    
    df["시작일"] = pd.to_datetime(df["시작일"], errors='coerce')
    df["종료일"] = pd.to_datetime(df["종료일"], errors='coerce')
    today = pd.to_datetime(datetime.today().strftime("%Y-%m-%d"))
    df["남은기간"] = (df["종료일"] - today).dt.days.fillna(0).astype(int)

    if "진행률" in df.columns and df["진행률"].dtype == 'object':
        df["진행률"] = df["진행률"].astype(str).str.replace('%', '')
    df["진행률"] = pd.to_numeric(df["진행률"], errors='coerce').fillna(0).astype(int)
    
    df["진행상황"] = df["진행률"]
    if "_original_id" not in df.columns:
        df["_original_id"] = df.index
    
    return df

# 데이터 초기화
if 'data' not in st.session_state:
    try:
        raw_data = load_data_from_sheet()
        st.session_state['data'] = process_dataframe(raw_data)
    except Exception as e:
        st.error(f"⚠️ 데이터 불러오기 실패: {e}")
        st.stop()

data = st.session_state['data'].copy()
data["시작일"] = pd.to_datetime(data["시작일"], errors='coerce')
data["종료일"] = pd.to_datetime(data["종료일"], errors='coerce')
today = pd.to_datetime(datetime.today().strftime("%Y-%m-%d"))
data["남은기간"] = (data["종료일"] - today).dt.days.fillna(0).astype(int)
data["진행상황"] = data["진행률"]

# 리스트 추출
def get_unique_list(df, col_name):
    if col_name in df.columns:
        return sorted(df[col_name].astype(str).dropna().unique().tolist())
    return []

projects_list = get_unique_list(data, "프로젝트명")
items_list = get_unique_list(data, "구분")
members_list = get_unique_list(data, "담당자")
activity_list = get_unique_list(data, "Activity")

def wrap_labels(text, width=15):
    if pd.isna(text): return ""
    return "<br>".join(textwrap.wrap(str(text), width=width, break_long_words=True))

# -----------------------------------------------------------------------------
# 4. [시각화 섹션] 테이블형 간트차트
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
        column_widths=[0.12, 0.06, 0.06, 0.06, 0.70], 
        subplot_titles=("<b>프로젝트명</b>", "<b>구분</b>", "<b>담당자</b>", "<b>Activity</b>", ""),
        specs=[[{"type": "scatter"}, {"type": "scatter"}, {"type": "scatter"}, {"type": "scatter"}, {"type": "xy"}]]
    )

    num_rows = len(chart_data)
    y_axis = list(range(num_rows))

    # [수정] 모든 텍스트 컬럼 중앙 정렬 (middle center)
    common_props = dict(mode="text", textposition="middle center", textfont=dict(color="black", size=10), hoverinfo="skip")

    # Col 1: 프로젝트명 (middle center)
    fig.add_trace(go.Scatter(x=[0.5] * num_rows, y=y_axis, text=chart_data["프로젝트명_표시"], **common_props), row=1, col=1)
    # Col 2: 구분
    fig.add_trace(go.Scatter(x=[0.5] * num_rows, y=y_axis, text=chart_data["구분"], **common_props), row=1, col=2)
    # Col 3: 담당자
    fig.add_trace(go.Scatter(x=[0.5] * num_rows, y=y_axis, text=chart_data["담당자"], **common_props), row=1, col=3)
    # Col 4: Activity (middle center)
    fig.add_trace(go.Scatter(x=[0.5] * num_rows, y=y_axis, text=chart_data["Activity_표시"], **common_props), row=1, col=4)

    # Col 5: Bar Chart
    for idx, row in chart_data.iterrows():
        start_ms = row["시작일"].timestamp() * 1000
        end_ms = row["종료일"].timestamp() * 1000
        duration = end_ms - start_ms
        
        day_diff = (row["종료일"] - row["시작일"]).days + 1
        bar_text = f"{day_diff}일 / {row['진행률']}%"

        fig.add_trace(go.Bar(
            base=[start_ms], x=[duration], y=[idx],
            orientation='h',
            marker_color=color_map.get(row["담당자"], "grey"),
            opacity=0.8,
            hoverinfo="text",
            hovertext=f"{row['프로젝트명']}<br>{row['시작일'].strftime('%Y-%m-%d')} ~ {row['종료일'].strftime('%Y-%m-%d')}",
            text=bar_text, textposition='inside', insidetextanchor='middle',
            textfont=dict(color='black', size=10),
            showlegend=False
        ), row=1, col=5)
        
        # [수정] 담당자 이름 표기 삭제됨

    view_start = today - timedelta(days=3)
    view_end = today + timedelta(days=11)
    
    # 축 설정
    for i in range(1, 5):
        fig.update_xaxes(showgrid=False, zeroline=False, showticklabels=False, row=1, col=i)
        fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=False, row=1, col=i)

    fig.update_xaxes(
        type="date", range=[view_start, view_end], side="top",
        tickfont=dict(size=10, color="black"),
        gridcolor='rgba(0,0,0,0.1)', row=1, col=5
    )
    fig.update_yaxes(
        showticklabels=False, showgrid=False, 
        fixedrange=True, # 세로 줌 잠금
        row=1, col=5
    )

    fig.add_vline(x=today.timestamp() * 1000, line_width=2, line_dash="dash", line_color="rgba(255, 0, 0, 0.6)", row=1, col=5)

    shapes = []
    for i in range(num_rows + 1):
        shapes.append(dict(type="line", xref="paper", yref="y", x0=0, x1=1, y0=i-0.5, y1=i-0.5, line=dict(color="rgba(0,0,0,0.1)", width=1)))
    
    # [수정] 높이 계산 (최대 510, 행 높이 30)
    calculated_height = num_rows * 30 + 50
    chart_height = min(510, max(300, calculated_height))
    
    fig.update_layout(
        height=chart_height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor='white', plot_bgcolor='white',
        showlegend=False, shapes=shapes, dragmode="pan",
        title={
            'text': "Project Schedule",
            'y': 0.99, 'x': 0.3, 'xanchor': 'left', 'yanchor': 'top',
            'font': dict(size=15, color="#333333")
        }
    )
    
    fig.update_annotations(font=dict(size=15, color="black"))
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': True})
else:
    st.info("표시할 일정이 없습니다.")

# -----------------------------------------------------------------------------
# 5. [입력 섹션]
# -----------------------------------------------------------------------------
st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

with st.expander("➕ 새 일정 등록하기"):
    with st.form("add_task_form"):
        c1, c2, c3 = st.columns(3)
        def input_or_select(label, options, key):
            extended_options = options + ["➕ 직접 입력"]
            selected = st.selectbox(label, extended_options, key=f"{key}_sel")
            if selected == "➕ 직접 입력":
                return st.text_input(f"└ {label} 입력", key=f"{key}_txt")
            return selected

        with c1:
            final_name = input_or_select("1. 프로젝트명", projects_list, "proj")
            final_item = input_or_select("2. 구분", items_list, "item")
        with c2:
            final_member = input_or_select("3. 담당자", members_list, "memb")
            final_act = input_or_select("4. Activity", activity_list, "act")
        with c3:
            p_start = st.date_input("5. 시작일", datetime.today())
            p_end = st.date_input("6. 종료일", datetime.today())
            st.markdown("<br>", unsafe_allow_html=True)
            submit_btn = st.form_submit_button("저장", type="primary", use_container_width=True)
        
        if submit_btn:
            if not final_name:
                st.error("프로젝트명을 입력해주세요.")
            else:
                new_row = pd.DataFrame([{
                    "프로젝트명": final_name, "구분": final_item, "담당자": final_member,
                    "Activity": final_act, "시작일": p_start.strftime("%Y-%m-%d"),
                    "종료일": p_end.strftime("%Y-%m-%d"), "진행률": 0
                }])
                
                st.session_state['data'] = pd.concat([st.session_state['data'], new_row], ignore_index=True)
                
                try:
                    save_data = st.session_state['data'].copy()
                    if "_original_id" in save_data.columns:
                        save_data = save_data.drop(columns=["_original_id"])
                    
                    save_data["시작일"] = pd.to_datetime(save_data["시작일"]).dt.strftime("%Y-%m-%d")
                    save_data["종료일"] = pd.to_datetime(save_data["종료일"]).dt.strftime("%Y-%m-%d")
                    conn.update(worksheet="Sheet1", data=save_data)
                    load_data_from_sheet.clear()
                    st.success("추가되었습니다!")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"저장 실패: {e}")

# -----------------------------------------------------------------------------
# 6. [컨트롤 패널]
# -----------------------------------------------------------------------------
st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

# [수정] 간편 추가 버튼 삭제됨
# [제목: 0.22] [라벨: 0.08] [선택박스: 0.17] [정렬토글: 0.15] [완료토글: 0.38]
c_title, c_label, c_box, c_sort, c_show = st.columns([0.22, 0.08, 0.17, 0.15, 0.38])

with c_title:
    st.markdown('<div class="subheader-text no-print">📝 업무 현황</div>', unsafe_allow_html=True)

with c_label:
    st.markdown('<div class="sort-label no-print">정렬</div>', unsafe_allow_html=True)

with c_box:
    sort_col = st.selectbox("정렬", ["프로젝트명", "구분", "담당자", "시작일", "종료일", "진행률"], label_visibility="collapsed")

with c_sort:
    sort_asc = st.toggle("오름차순 정렬", value=True)

with c_show:
    show_completed = st.toggle("완료된 업무 보기", value=st.session_state['show_completed'])
    if show_completed != st.session_state['show_completed']:
        st.session_state['show_completed'] = show_completed
        st.rerun()

# -----------------------------------------------------------------------------
# 7. 데이터 에디터 및 저장
# -----------------------------------------------------------------------------
filtered_df = st.session_state['data'].copy()
if not st.session_state['show_completed']:
    filtered_df = filtered_df[filtered_df["진행률"] < 100]

filtered_df = filtered_df.sort_values(by=sort_col, ascending=sort_asc)

st.markdown('<div class="no-print" style="color:gray; font-size:0.8rem; margin-bottom:5px;">※ 내용을 수정한 후 <b>저장</b> 버튼을 꼭 누르세요. (브라우저 인쇄: Ctrl+P)</div>', unsafe_allow_html=True)

display_cols = ["프로젝트명", "구분", "담당자", "Activity", "시작일", "종료일", "남은기간", "진행률", "진행상황"]
final_display_cols = [c for c in display_cols if c in filtered_df.columns]

dynamic_height = (len(filtered_df) + 1) * 35 + 3

edited_df = st.data_editor(
    filtered_df,
    height=dynamic_height,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "프로젝트명": st.column_config.SelectboxColumn("프로젝트명", options=projects_list, required=True),
        "구분": st.column_config.SelectboxColumn("구분", options=items_list),
        "담당자": st.column_config.SelectboxColumn("담당자", options=members_list),
        "Activity": st.column_config.SelectboxColumn("Activity", options=activity_list),
        "진행률": st.column_config.NumberColumn("진행률", min_value=0, max_value=100, step=5, format="%d"),
        "진행상황": st.column_config.ProgressColumn("진행상황(Bar)", format="%d%%", min_value=0, max_value=100),
        "시작일": st.column_config.DateColumn("시작일", format="YYYY-MM-DD"),
        "종료일": st.column_config.DateColumn("종료일", format="YYYY-MM-DD"),
        "남은기간": st.column_config.NumberColumn("남은기간(일)", format="%d일", disabled=True),
    },
    column_order=final_display_cols,
    hide_index=True,
    key="data_editor"
)

# [수정] 쿼터 초과 방지 및 데이터 무결성 확보 로직
if st.button("💾 변경사항 저장하기", type="primary"):
    try:
        with st.spinner("저장 중..."):
            edited_part = edited_df.copy()
            full_data = st.session_state['data'].copy()
            
            if "_original_id" in full_data.columns and "_original_id" in edited_part.columns:
                full_data.set_index("_original_id", inplace=True)
                edited_part.set_index("_original_id", inplace=True)
                full_data.update(edited_part)
                full_data.reset_index(inplace=True)
                
                save_df = full_data.copy()
                save_df["시작일"] = pd.to_datetime(save_df["시작일"]).dt.strftime("%Y-%m-%d").fillna("")
                save_df["종료일"] = pd.to_datetime(save_df["종료일"]).dt.strftime("%Y-%m-%d").fillna("")
                save_df["진행률"] = pd.to_numeric(save_df["진행률"]).fillna(0).astype(int)
                
                # 구글 시트에 업데이트
                conn.update(worksheet="Sheet1", data=save_df)
                
                # 캐시 초기화 및 세션 갱신
                load_data_from_sheet.clear()
                st.session_state['data'] = process_dataframe(save_df)
                
                st.success("저장되었습니다.")
                time.sleep(1) # [API 쿼터 방지] 너무 빠른 리프레시 방지
                st.rerun()
            else:
                st.error("데이터 병합 오류: 고유 ID를 찾을 수 없습니다.")
    except Exception as e:
        st.error(f"저장 중 오류 발생: {e}")
