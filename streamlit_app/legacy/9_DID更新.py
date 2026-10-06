"""
DID 更新

先查询当前 DID 文档，允许用户编辑 JSON，再调用 /api/did/update 提交更新。
"""

from __future__ import annotations

import json

import streamlit as st

from components.renderers import page_header, render_json_block
from services.data_service import api_latest, api_update
from utils.validators import parse_json_text, validate_did


page_header("DID 更新", "先查询当前文档，再编辑 JSON，最后调用 /api/did/update。")

if "update_editor_text" not in st.session_state:
    st.session_state.update_editor_text = "{}"

source_did = st.text_input("请输入需要更新的 DID", placeholder="例如：did:ethr:alice")

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("加载当前文档", type="primary"):
        try:
            did_value = validate_did(source_did)
            latest = api_latest(did_value)
            current = latest.get("current_document") or latest.get("currentDocument") or {}
            document = current.get("document", {})
            st.session_state.update_editor_text = json.dumps(document, ensure_ascii=False, indent=2)
            st.success("当前文档已加载")
        except Exception as exc:
            st.error(f"加载失败：{exc}")

editor_text = st.text_area("编辑后的 DID 文档 JSON", height=360, key="update_editor_text")
manual_version = st.number_input("可选：指定版本号", min_value=0, step=1, value=0)

if st.button("提交更新"):
    try:
        did_value = validate_did(source_did)
        document = parse_json_text(editor_text)
        version = int(manual_version) if int(manual_version) > 0 else None
        result = api_update(did_value, document, version)
        st.success("DID 更新成功")
        render_json_block("update_result", result)
    except Exception as exc:
        st.error(f"更新失败：{exc}")