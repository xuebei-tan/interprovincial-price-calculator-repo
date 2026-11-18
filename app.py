from pathlib import Path

import pandas as pd
import streamlit as st

from calculator import PowerTradeCalculator

APP_DIR = Path(__file__).resolve().parent
PARAMETER_FILE = APP_DIR / "跨省线路信息表.xlsx"

st.set_page_config(
    page_title="跨省电力落地价格测算",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      .block-container {max-width: 1200px; padding-top: 2rem; padding-bottom: 3rem;}
      div[data-testid="stMetric"] {background:#f4f7f6; border:1px solid #d8e1de; padding:18px; border-radius:10px;}
      .subtitle {color:#59636b; margin-top:-10px; margin-bottom:24px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("跨省电力落地价格测算")
st.markdown('<div class="subtitle">Inter-provincial Power Cost Calculator</div>', unsafe_allow_html=True)

if not PARAMETER_FILE.exists():
    st.error("缺少参数文件：跨省线路信息表.xlsx")
    st.info("请将原参数表放在 app.py 同一目录，并确认文件名完全一致。")
    st.stop()


@st.cache_resource(show_spinner="正在加载线路参数……")
def load_calculator(file_path: str, modified_ns: int) -> PowerTradeCalculator:
    del modified_ns
    return PowerTradeCalculator(file_path)


try:
    calculator = load_calculator(str(PARAMETER_FILE), PARAMETER_FILE.stat().st_mtime_ns)
except Exception as exc:
    st.error("参数表加载失败。")
    st.exception(exc)
    st.stop()

with st.form("calculator_form", clear_on_submit=False):
    left, right = st.columns(2, gap="large")
    with left:
        from_province = st.selectbox("送出省份 / From Province", calculator.provinces)
        energy_price = st.number_input(
            "送端电能量价格 / Energy Price (RMB/MWh)",
            min_value=0.0, value=210.0, step=1.0, format="%.3f",
        )
    with right:
        default_to_index = 1 if len(calculator.provinces) > 1 else 0
        to_province = st.selectbox("受入省份 / To Province", calculator.provinces, index=default_to_index)
        green_premium = st.number_input(
            "环境权益价格 / Green Premium (RMB/MWh)",
            min_value=0.0, value=0.0, step=1.0, format="%.3f",
        )
    submitted = st.form_submit_button("开始测算 / Calculate", type="primary", use_container_width=True)

if submitted:
    if from_province == to_province:
        st.warning("送出省份和受入省份不能相同。")
        st.stop()

    with st.spinner("正在搜索可行路径并计算落地价格……"):
        routes = calculator.search_all(from_province, to_province, energy_price, green_premium)

    if not routes:
        st.error("未找到可行路线，请检查参数表中的线路拓扑和启用状态。")
        st.stop()

    best = routes[0]
    st.divider()
    metric_col, route_col = st.columns([1, 2], gap="large")
    with metric_col:
        st.metric("最低落地价格", f"{best['price']:,.3f} 元/MWh")
        st.caption(f"共找到 {len(routes)} 条不重复路径")
    with route_col:
        st.subheader("最优路径")
        st.write(best["path_str"])

    st.subheader("最优路径费用明细")
    detail_df = pd.DataFrame(best["details"])
    detail_df["网损率"] = detail_df["网损率"].map(lambda value: f"{value * 100:.3f}%")
    for column in ["输电价", "基准价", "网损折价", "结算价"]:
        detail_df[column] = detail_df[column].map(lambda value: round(float(value), 3))
    st.dataframe(detail_df, use_container_width=True, hide_index=True)

    st.subheader("可行路径比较")
    summary_df = pd.DataFrame([
        {"排名": index + 1, "路径": route["path_str"], "落地价格（元/MWh）": route["price"]}
        for index, route in enumerate(routes[:10])
    ])
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    with st.expander("查看其他路径的分环节明细"):
        route_number = st.selectbox(
            "选择路径",
            options=range(len(routes[:10])),
            format_func=lambda index: f"路线 {index + 1} · {routes[index]['price']:.3f} 元/MWh",
        )
        selected = routes[route_number]
        st.write(selected["path_str"])
        selected_df = pd.DataFrame(selected["details"])
        selected_df["网损率"] = selected_df["网损率"].map(lambda value: f"{value * 100:.3f}%")
        st.dataframe(selected_df, use_container_width=True, hide_index=True)

st.caption(f"参数文件：{PARAMETER_FILE.name} · 参数省份数量：{len(calculator.provinces)}")
