"""
Streamlit 可视化平台首页

本模块是基于 Streamlit 的去中心化身份认证系统可视化平台入口页面。
页面布局分为三部分：
左侧显示后端健康状态与 Flask API 连接情况；
右侧展示 MongoDB 中各业务集合的文档数量概览；
底部给出典型实验操作流程建议。

该页面是“中文可视化平台”，面向调试、实验展示与答辩演示场景，
不替代微信小程序作为用户客户端。
"""

from __future__ import annotations

import os

import streamlit as st

from components.renderers import page_header, render_json_block
from services.api_client import BACKEND_BASE_URL
from services.data_service import backend_health, collection_counts
from services.mongo_client import MONGO_DB_NAME, MONGO_URI


st.set_page_config(
    page_title="DID 系统可视化平台",
    page_icon="🧩",
    layout="wide",
    initial_sidebar_state="expanded",
)

page_header(
    "基于区块链的不可信存储环境去中心化身份认证系统",
)

st.markdown(
    """
### 流程
1. **链上是最新可信状态**：链上只保存状态与摘要，不保存完整 DID 文档。  
2. **链下是完整数据载体**：MongoDB 保存当前文档、历史版本、恢复块、验证记录与实验记录。  
3. **可信判断在后端完成**：前端只负责发起请求与展示结果，不自行宣告“验证通过”。  
4. **Streamlit 属于系统观测层**：适合展示链上链下对比、版本历史、验证过程与实验统计。  
"""
)

with st.sidebar:
    st.subheader("运行配置")
    st.write(
        {
            "后端地址": BACKEND_BASE_URL,
            "Mongo URI": MONGO_URI,
            "Mongo 数据库": MONGO_DB_NAME,
            "Streamlit 端口": os.getenv("STREAMLIT_SERVER_PORT", "8501"),
        }
    )
    st.info("操作类页面会调用 Flask API；展示类页面直接读取 MongoDB。")

left_col, right_col = st.columns([1, 2])

with left_col:
    st.subheader("后端健康状态")
    try:
        health_payload = backend_health()
        st.success("Flask 后端联通正常")
        render_json_block("健康检查响应", health_payload)
    except Exception as exc:
        st.error(f"后端连接失败：{exc}")

with right_col:
    st.subheader("链下集合数量")
    try:
        counts = collection_counts()
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("当前文档", counts.get("did_documents", 0))
        c2.metric("历史版本", counts.get("did_versions", 0))
        c3.metric("验证记录", counts.get("verification_records", 0))
        c4.metric("恢复块", counts.get("did_recovery_blocks", 0))
        c5.metric("实验记录", counts.get("experiment_records", 0))
    except Exception as exc:
        st.error(f"MongoDB 读取失败：{exc}")

