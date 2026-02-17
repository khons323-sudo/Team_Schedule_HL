import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots # [필수] 테이블형 차트를 위해 필요
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import time
import textwrap 

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 디자인 CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="디자인1본부 일정관리", layout="wide")

custom_css = """
<style>
    .title-text { font-size: 1.3rem !important; font-weight: 700; color: rgb(49, 51, 63); }
    .subheader-text { font-size: 1.2rem; font-weight: 600; }
    .block-container { padding-top: 1rem !important; padding-bottom: 2rem !important; }
    div[data-testid="stForm"] .stSelectbox { margin-bottom: -15px !important; }
    div[data-testid="stForm"] .stTextInput { margin-top: 0px !important; }
    .sort-label { font-size: 14px; font-weight: 600; display: flex; align-items: center; justify-content: flex-end; height: 40px; padding-right: 10px; }
    div[data-testid="stSelectbox"] { margin-top: 2px; }
    div[data-testid="stCheckbox"] { margin-top: 8px; }
    div[data-testid="stCheckbox"] label { font-size: 14px !important; }
    div[data-testid="stPopover"] button { margin-top: 8px; font-weight: bold; }

    @media print {
        header, footer, aside, [data-testid="stSidebar"], [data-testid="stToolbar"], 
        .stButton, .stDownloadButton, .stExpander, .stForm, 
        div[data-testid="stVerticalBlockBorderWrapper"], button,
        .no-print, .sort-area, .stSelectbox, .stCheckbox, div[data-testid="stPopover"] 
        { display: none !important; }

        body, .stApp { background-color: white !important; -webkit-print-color-adjust: exact !important; zoom: 75%; }
        * { color: black !important; text-shadow: none !important; }
        .main .block-container { max-width: 100% !important; width: 100% !important; padding: 0 !important; margin: 0 !important; }
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] { height: auto !important; width: 100% !important; overflow: visible !important; display: block !important; }
        div[data-testid="stDataEditor"], .js-plotly-plot { break-inside: avoid !important; margin-bottom: 20px !important; width: 100% !important; }
        div[data-testid="stDataEditor"] table { font-size: 11px !important; border: 1px solid #000
