"""
DID 恢复

调用 /api/did/recover 接口，展示恢复方式（副本或纠删码）以及恢复后的本地和链上完整性校验结果。
"""

from __future__ import annotations

import streamlit as st

from components.renderers import page_header, render_json_block, render_result_flag
from services.data_service import api_recover
from utils.validators import validate_did


page_header("DID 恢复", "调用 /api/did/recover，展示恢复方式与恢复后校验结果。")

with st.form("recover_form"):
    did = st.text_input("DID", placeholder="例如：did:ethr:alice")
    version = st.number_input("可选：指定版本号", min_value=0, step=1, value=0)
    force_method = st.selectbox("恢复方式", options=["", "replica", "erasure"], index=0)
    missing_indexes_text = st.text_input("缺失分片索引（可选，英文逗号分隔）", placeholder="例如：1,3")
    submitted = st.form_submit_button("执行恢复", type="primary")

if submitted:
    try:
        did_value = validate_did(did)
        missing_indexes: list[int] | None = None
        if missing_indexes_text.strip():
            missing_indexes = [int(item.strip()) for item in missing_indexes_text.split(",") if item.strip()]
        result = api_recover(
            did_value,
            int(version) if int(version) > 0 else None,
            force_method or None,
            missing_indexes,
        )
        render_json_block("recover_result", result)
        render_result_flag("恢复后本地完整性", bool(result.get("local_integrity_ok")))
        render_result_flag("恢复后链上一致性", bool(result.get("chain_integrity_ok")))
        render_result_flag("整体恢复有效性", bool(result.get("is_valid")))
    except Exception as exc:
        st.error(f"恢复失败：{exc}")