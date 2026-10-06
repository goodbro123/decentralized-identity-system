"""
DID 列表

展示链下 `did_documents` 集合的当前视图，支持关键词搜索与条数限定。
适合快速检索已有 DID，查看版本、哈希摘要等关键信息。
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.renderers import page_header, render_json_block
from services.data_service import list_current_documents
from utils.formatters import short_hash


page_header("DID 列表", "展示链下 did_documents 当前视图，适合快速检索已有 DID。")

keyword = st.text_input("关键词搜索", placeholder="可输入 DID / 姓名 / 组织")
limit = st.slider("最多显示条数", min_value=10, max_value=300, value=100, step=10)

try:
    documents = list_current_documents(keyword=keyword, limit=limit)
except Exception as exc:
    st.error(f"读取 did_documents 失败：{exc}")
    st.stop()

if not documents:
    st.info("没有找到匹配的数据")
    st.stop()

rows = []
for item in documents:
    rows.append(
        {
            "did": item.get("did"),
            "version": item.get("version"),
            "status": item.get("status"),
            "document_hash": short_hash(item.get("document_hash") or item.get("doc_hash")),
            "merkle_root": short_hash(item.get("merkle_root")),
            "version_hash": short_hash(item.get("version_hash")),
            "updated_at": str(item.get("updated_at", "-")),
        }
    )

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

selected_did = st.selectbox("查看完整记录", options=[item.get("did") for item in documents])
selected = next((item for item in documents if item.get("did") == selected_did), None)
if selected:
    render_json_block("当前 DID 完整记录", selected)