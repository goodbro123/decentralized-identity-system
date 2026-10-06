"""
属性证明

调用 /api/did/proof 接口，生成指定属性路径的默克尔包含证明，并展示证明详情。
"""

from __future__ import annotations

import streamlit as st

from components.renderers import page_header, render_json_block
from services.data_service import api_proof
from utils.validators import validate_did


page_header("属性证明", "调用 /api/did/proof，展示属性级默克尔证明。")

with st.form("proof_form"):
    did = st.text_input("DID", placeholder="例如：did:ethr:alice")
    attribute_path = st.text_input("属性路径", placeholder="例如：profile.organization")
    version = st.number_input("可选：指定版本号", min_value=0, step=1, value=0)
    submitted = st.form_submit_button("生成属性证明", type="primary")

if submitted:
    try:
        did_value = validate_did(did)
        result = api_proof(
            did_value,
            attribute_path.strip(),
            int(version) if int(version) > 0 else None,
        )
        render_json_block("proof_result", result)
    except Exception as exc:
        st.error(f"生成属性证明失败：{exc}")