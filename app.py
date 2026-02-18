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
# 1. 페이지 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="디자인1본부 일정관리", layout="wide")

st.markdown("### 📅 디자인1본부 1팀 일정")

# -----------------------------------------------------------------------------
# 2. 데이터 로드 (Cloud 안정화)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="Sheet1")
    return df

def process_dataframe(df):
    if df.empty:
        return pd.DataFrame(columns=["프로젝트명","구분","담당자","Activity","시작일","종료일","진행률"])

    df["시작일"] = pd.to_datetime(df["시작일"], errors="coerce")
    df["종료일"] = pd.to_datetime(df["종료일"], errors="coerce")
    df["진행률"] = pd.to_numeric(df["진행률"], errors="coerce").fillna(0).astype(int)

    today = pd.to_datetime(datetime.today().strftime("%Y-%m-%d"))
    df["남은기간"] = (df["종료일"] - today).dt.days.fillna(0).astype(int)
    df["진행상황"] = df["진행률"]

    if "_original_id" not in df.columns:
        df["_original_id"] = df.index

    return df

if "data" not in st.session_state:
    raw = load_data()
    st.session_state["data"] = process_dataframe(raw)

data = st.session_state["data"].copy()

# -----------------------------------------------------------------------------
# 3. 간트 차트 (Cloud 안정 버전)
# -----------------------------------------------------------------------------
chart_data = data.dropna(subset=["시작일","종료일"]).copy()
chart_data = chart_data[chart_data["진행률"] < 100]

if not chart_data.empty:

    chart_data = chart_data.sort_values(by=["프로젝트명","시작일"]).reset_index(drop=True)

    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.25,0.75],
        shared_yaxes=True,
        horizontal_spacing=0.02,
        specs=[[{"type":"scatter"},{"type":"xy"}]]
    )

    y_axis = list(range(len(chart_data)))

    # 좌측 텍스트
    fig.add_trace(
        go.Scatter(
            x=[0]*len(chart_data),
            y=y_axis,
            text=chart_data["프로젝트명"],
            mode="text",
            textposition="middle right",
            hoverinfo="skip"
        ),
        row=1,col=1
    )

    # 우측 바 차트
    for idx,row in chart_data.iterrows():
        fig.add_trace(
            go.Bar(
                x=[row["종료일"]-row["시작일"]],
                base=row["시작일"],
                y=[idx],
                orientation="h",
                text=f"{row['진행률']}%",
                textposition="inside",
                showlegend=False
            ),
            row=1,col=2
        )

    today = pd.to_datetime(datetime.today().strftime("%Y-%m-%d"))

    # 날짜 범위 (2주 제한 → tick 폭발 방지)
    view_start = today - timedelta(days=3)
    view_end = today + timedelta(days=14)

    fig.update_xaxes(
        type="date",
        range=[view_start,view_end],
        row=1,col=2
    )

    # timestamp 제거 → date 직접 사용
    fig.add_vline(x=today, line_width=2, line_dash="dash", line_color="red", row=1,col=2)

    # 높이 제한
    fig.update_layout(
        height=min(700, len(chart_data)*40 + 200),
        margin=dict(l=10,r=10,t=50,b=10),
        dragmode="pan"
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("표시할 일정이 없습니다.")

# -----------------------------------------------------------------------------
# 4. 데이터 에디터 (높이 제한)
# -----------------------------------------------------------------------------
filtered_df = st.session_state["data"].copy()

filtered_df = filtered_df.sort_values(by="프로젝트명")

dynamic_height = min((len(filtered_df)+1)*35+5, 800)

edited_df = st.data_editor(
    filtered_df,
    height=dynamic_height,
    use_container_width=True,
    hide_index=True
)

# -----------------------------------------------------------------------------
# 5. 저장 버튼
# -----------------------------------------------------------------------------
if st.button("💾 변경사항 저장하기", type="primary"):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)

        save_df = edited_df.copy()
        save_df["시작일"] = pd.to_datetime(save_df["시작일"]).dt.strftime("%Y-%m-%d")
        save_df["종료일"] = pd.to_datetime(save_df["종료일"]).dt.strftime("%Y-%m-%d")

        conn.update(worksheet="Sheet1", data=save_df)

        st.cache_data.clear()
        st.success("저장 완료!")
        time.sleep(0.5)
        st.rerun()

    except Exception as e:
        st.error(f"저장 오류: {e}")
