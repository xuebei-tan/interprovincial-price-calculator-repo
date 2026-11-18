from pathlib import Path
import html
import pandas as pd
import streamlit as st
from calculator import PowerTradeCalculator

ROOT = Path(__file__).resolve().parent
PARAMETER_FILE = ROOT / "跨省线路信息表.xlsx"

st.set_page_config(page_title="跨省电力落地价格测算", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
:root {--green:#00793a;--ink:#17211d;--muted:#6d7772;--line:#dfe6e2;--soft:#f5f8f6;--warm:#fbfaf7;}
.block-container{max-width:1280px;padding-top:1.3rem;padding-bottom:4rem}.stApp{background:#fff;color:var(--ink)}
header[data-testid="stHeader"]{background:transparent}.hero{padding:18px 0 8px;border-bottom:1px solid var(--line);margin-bottom:20px}
.kicker{font-size:.72rem;letter-spacing:.16em;color:var(--green);font-weight:700}.hero h1{font-size:2.05rem;margin:.25rem 0 .15rem;letter-spacing:-.025em}.hero p{color:var(--muted);margin:0 0 .7rem}
[data-testid="stForm"]{border:0!important;padding:0!important}.stSelectbox label,.stNumberInput label{font-weight:650;color:var(--ink)}
div[data-testid="stFormSubmitButton"] button{background:var(--green);color:white;border:0;border-radius:4px;min-height:45px;font-weight:700}
div[data-testid="stFormSubmitButton"] button:hover{background:#006631;color:white}
.price-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 0 24px}.price-card{background:var(--soft);border:1px solid var(--line);padding:15px 16px;border-radius:5px}.price-card.best{background:#eef7f1;border-color:#9cc9ad}.price-label{font-size:.72rem;color:var(--muted);letter-spacing:.08em;text-transform:uppercase}.price-value{font-weight:750;font-size:1.55rem;margin-top:4px}.price-unit{font-size:.72rem;color:var(--muted)}
.section-title{display:flex;justify-content:space-between;align-items:end;border-bottom:2px solid var(--ink);margin:24px 0 8px;padding-bottom:7px}.section-title b{font-size:1.02rem}.section-title span{font-size:.7rem;color:var(--muted);letter-spacing:.12em}
.route-card{border:1px solid var(--line);border-left:4px solid #aab5af;border-radius:5px;padding:15px 17px;margin:10px 0;background:#fff}.route-card.best{border-left-color:var(--green);background:#fbfdfb}.route-top{display:flex;align-items:flex-start;justify-content:space-between;gap:18px}.route-rank{font-size:.7rem;color:var(--muted);font-weight:700;letter-spacing:.08em}.route-path{font-size:1.03rem;font-weight:700;margin-top:3px}.route-price{text-align:right;white-space:nowrap}.route-price strong{font-size:1.2rem}.route-price small{display:block;color:var(--muted)}
div[data-testid="stExpander"]{border:1px solid var(--line);border-radius:5px;margin-top:-11px;margin-bottom:12px}div[data-testid="stExpander"] summary{font-weight:650;color:#33423b}
.note{background:var(--warm);border-left:3px solid #ae9a71;padding:12px 14px;color:#5e594f;font-size:.88rem;margin-top:24px}.foot{color:var(--muted);font-size:.75rem;margin-top:28px;padding-top:12px;border-top:1px solid var(--line)}
@media(max-width:800px){.price-grid{grid-template-columns:repeat(2,1fr)}.route-top{display:block}.route-price{text-align:left;margin-top:8px}}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><div class="kicker">PROVINCE-PAIR POWER PRICING</div><h1>跨省电力落地价格测算</h1><p>选择送出省与受入省，输入送端电能量价格和环境权益价格，比较所有可行输电路径。</p></div>', unsafe_allow_html=True)

if not PARAMETER_FILE.exists():
    st.error("缺少参数文件：跨省线路信息表.xlsx")
    st.stop()

@st.cache_resource
def get_calc(path, mtime):
    return PowerTradeCalculator(path)

try:
    calc = get_calc(str(PARAMETER_FILE), PARAMETER_FILE.stat().st_mtime_ns)
except Exception as exc:
    st.error("参数表加载失败")
    st.exception(exc)
    st.stop()

# Persist results so opening route details never requires re-entering/recalculating.
if "routes" not in st.session_state: st.session_state.routes = None
if "query" not in st.session_state: st.session_state.query = None

with st.form("pricing", clear_on_submit=False):
    a,b = st.columns(2, gap="large")
    with a:
        from_p = st.selectbox("送出省份  FROM", calc.provinces, key="from_p")
        energy = st.number_input("送端电能量电价  ENERGY PRICE (元/MWh)", min_value=0.0, value=210.0, step=1.0, format="%.3f")
    with b:
        default_idx = 1 if len(calc.provinces)>1 else 0
        to_p = st.selectbox("落地省份  TO", calc.provinces, index=default_idx, key="to_p")
        green = st.number_input("环境权益价格  GREEN PREMIUM (元/MWh)", min_value=0.0, value=0.0, step=1.0, format="%.3f")
    submitted = st.form_submit_button("开始测算  CALCULATE", use_container_width=True, type="primary")

if submitted:
    if from_p == to_p:
        st.warning("送出省份和落地省份不能相同。")
        st.session_state.routes = None
    else:
        with st.spinner("正在搜索可行路径……"):
            st.session_state.routes = calc.search_all(from_p, to_p, energy, green)
            st.session_state.query = {"from":from_p,"to":to_p,"energy":energy,"green":green}

routes = st.session_state.routes
query = st.session_state.query
if routes == []:
    st.error("未找到可行路径。")
elif routes and query:
    best = routes[0]
    transmission_loss = best["price"] - query["energy"] - query["green"]
    st.markdown(f'''<div class="section-title"><b>价格一览</b><span>PRICES</span></div>
    <div class="price-grid">
      <div class="price-card"><div class="price-label">送端电能量</div><div class="price-value">{query['energy']:,.3f}</div><div class="price-unit">RMB/MWh</div></div>
      <div class="price-card"><div class="price-label">环境权益</div><div class="price-value">{query['green']:,.3f}</div><div class="price-unit">RMB/MWh</div></div>
      <div class="price-card"><div class="price-label">输电及网损增量</div><div class="price-value">{transmission_loss:,.3f}</div><div class="price-unit">RMB/MWh</div></div>
      <div class="price-card best"><div class="price-label">最低落地总价</div><div class="price-value">{best['price']:,.3f}</div><div class="price-unit">RMB/MWh</div></div>
    </div>''', unsafe_allow_html=True)

    st.markdown(f'<div class="section-title"><b>可行通道</b><span>ROUTES · {len(routes)} FOUND</span></div>', unsafe_allow_html=True)

    # All routes are rendered simultaneously as independent cards/expanders. No selectbox => no selection rerun/jump.
    for idx, route in enumerate(routes[:20]):
        is_best = idx == 0
        badge = " · 最低落地价" if is_best else ""
        klass = "route-card best" if is_best else "route-card"
        st.markdown(f'''<div class="{klass}"><div class="route-top"><div><div class="route-rank">ROUTE {idx+1:02d}{badge}</div><div class="route-path">{html.escape(route['path_str'])}</div></div><div class="route-price"><strong>{route['price']:,.3f}</strong><small>RMB/MWh</small></div></div></div>''', unsafe_allow_html=True)
        with st.expander(f"查看路线 {idx+1:02d} 分环节明细", expanded=is_best):
            df = pd.DataFrame(route["details"]).copy()
            df["网损率"] = df["网损率"].map(lambda x: f"{float(x)*100:.3f}%")
            for c in ["输电价","基准价","网损折价","结算价"]:
                df[c] = df[c].map(lambda x: round(float(x),3))
            st.dataframe(df, use_container_width=True, hide_index=True, column_config={
                "环节": st.column_config.TextColumn("环节名称", width="large"),
                "输电价": st.column_config.NumberColumn("输电价", format="%.3f"),
                "基准价": st.column_config.NumberColumn("基准价", format="%.3f"),
                "网损折价": st.column_config.NumberColumn("网损折价", format="%.3f"),
                "结算价": st.column_config.NumberColumn("结算价", format="%.3f"),
            })

    st.markdown('<div class="note"><b>测算说明</b>：环境权益价格不参与网损折价与输配电费计算；页面结果用于路径和价格比较，最终以实际交易及结算规则为准。</div>', unsafe_allow_html=True)

st.markdown(f'<div class="foot">参数文件：{html.escape(PARAMETER_FILE.name)} · 参数省份：{len(calc.provinces)} · 单位：元/MWh</div>', unsafe_allow_html=True)
