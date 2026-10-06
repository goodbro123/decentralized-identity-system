"""
DID 验证

调用 /api/did/verify 接口，展示链上链下一致性校验结果，包括文档哈希、默克尔根、版本链连续性及交易有效性等关键指标。
"""

from __future__ import annotations

import streamlit as st

from components.renderers import page_header, render_json_block, render_result_flag
from services.data_service import api_verify
from utils.validators import validate_did


page_header("DID 验证", "调用 /api/did/verify，展示链上链下一致性结论。")

with st.form("verify_form"):
    did = st.text_input("DID", placeholder="例如：did:ethr:alice")
    version = st.number_input("可选：指定版本号", min_value=0, step=1, value=0)
    submitted = st.form_submit_button("执行验证", type="primary")

if submitted:
    try:
        did_value = validate_did(did)
        result = api_verify(did_value, int(version) if int(version) > 0 else None)
        render_json_block("verify_result", result)
        render_result_flag("整体有效性", bool(result.get("is_valid")))
        render_result_flag("目标文档哈希一致", bool(result.get("target_document_hash_match")))
        render_result_flag("目标默克尔根一致", bool(result.get("target_merkle_root_match")))
        render_result_flag("版本链连续", bool(result.get("history_chain_valid")))
        render_result_flag("链上交易有效", bool(result.get("transaction_verified")))
    except Exception as exc:
        st.error(f"验证失败：{exc}")