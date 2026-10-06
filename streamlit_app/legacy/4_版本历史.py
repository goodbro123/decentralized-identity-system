"""
版本历史

展示 `did_versions` 集合中指定 DID 的所有历史版本，包括版本号、各哈希摘要、
前驱版本哈希以及变更属性数量，支持查看某个版本的完整原始记录。
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.renderers import page_header, render_json_block
from services.data_service import get_version_history
from utils.formatters import short_hash
from utils.validators import validate_did


page_header("版本历史", "展示 did_versions 中的历史版本、前驱哈希和变更属性。")

did_input = st.text_input("请输入 DID", placeholder="例如：did:ethr:alice")
limit = st.slider("显示版本数量", min_value=5, max_value=200, value=50, step=5)

if st.button("加载历史版本", type="primary"):
    try:
        did = validate_did(did_input)
        rows = get_version_history(did, limit)
    except Exception as exc:
        st.error(f"读取历史失败：{exc}")
        st.stop()

    if not rows:
        st.info("该 DID 暂无历史记录")
        st.stop()

    table_rows = []
    for item in rows:
        table_rows.append(
            {
                "version": item.get("version"),
                "transaction_hash": short_hash(item.get("transaction_hash")),
                "document_hash": short_hash(item.get("document_hash") or item.get("doc_hash")),
                "merkle_root": short_hash(item.get("merkle_root")),
                "version_hash": short_hash(item.get("version_hash")),
                "previous_version_hash": short_hash(item.get("previous_version_hash")),
                "changed_count": len(item.get("changed_attributes", [])),
                "updated_at": str(item.get("updated_at", "-")),
            }
        )

    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    selected_version = st.selectbox("查看某个版本的完整记录", options=[int(item.get("version")) for item in rows])
    selected = next((item for item in rows if int(item.get("version")) == int(selected_version)), None)
    if selected:
        render_json_block(f"version={selected_version} 完整记录", selected)