# 跨省电力落地价格测算工具

基于 Streamlit 的跨省电力落地价格计算界面，计算引擎保留原 Python + pandas + NetworkX 逻辑。

## 项目结构

```text
.
├── app.py
├── calculator.py
├── 跨省线路信息表.xlsx
├── requirements.txt
├── .streamlit/config.toml
└── .gitignore
```

> 必须把原始 `跨省线路信息表.xlsx` 放在项目根目录，与 `app.py` 同级。

## 本地运行

建议使用 Python 3.12：

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

macOS/Linux：

```bash
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

浏览器打开 `http://localhost:8501`。

## Streamlit Community Cloud 部署

1. 在 GitHub 创建一个 private repository。
2. 上传本项目全部文件，包括参数工作簿。
3. 登录 Streamlit Community Cloud，选择 **Create app**。
4. 选择 repository、`main` branch 和入口文件 `app.py`。
5. 在 Advanced settings 中选择 Python 3.12。
6. 部署后测试所有典型省份组合和价格输入。

## SharePoint 嵌入

部署完成后，可尝试在 SharePoint 页面添加 **Embed** Web Part，使用：

```text
https://你的应用.streamlit.app/?embed=true
```

是否允许嵌入取决于 SharePoint 站点的外部域和 iframe 安全策略。Community Cloud 私有应用也可能无法在 iframe 中完成登录。

## 数据与安全

Streamlit Community Cloud 和 GitHub 都是外部托管服务。上传前应确认参数表的数据分类允许外部存储。不要把密码、token、账号密钥或私密连接字符串写进代码或 Excel。

## 参数表要求

工作簿必须包含以下三个工作表：

- `A省级电网参数及外送特例`
- `B跨省跨区专项工程参数及拓扑`
- `C区域电网输电参数`

应用启动时会校验关键列。如列名被改动，会在页面显示缺失列信息。
