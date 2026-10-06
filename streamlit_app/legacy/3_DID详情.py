"""
DID 详情

查看指定 DID 的链上状态、链下当前文档和最新历史版本记录，并支持一键完整性验证。
"""

from __future__ import annotations

import streamlit as st

from components.renderers import page_header, render_hash_compare, render_json_block, render_result_flag
from services.data_service import api_latest, api_verify
from utils.validators import validate_did


page_header("DID 详情", "查看链上状态、链下当前文档和最新历史记录，并支持一键验证。")

did_input = st.text_input("请输入 DID", placeholder="例如：did:ethr:alice")

if st.button("查询 DID 详情", type="primary"):
    try:
        did = validate_did(did_input)
        result = api_latest(did)
    except Exception as exc:
        st.error(f"查询失败：{exc}")
        st.stop()

    chain_state = result.get("chain_state") or result.get("chainState") or {}
    current_document = result.get("current_document") or result.get("currentDocument") or {}
    latest_version_record = result.get("latest_version_record") or result.get("latestVersionRecord") or {}

    left, right = st.columns(2)
    with left:
        render_json_block("链上状态 chain_state", chain_state)
    with right:
        render_json_block("链下当前文档 current_document", current_document)

    st.subheader("摘要对比")
    render_hash_compare(
        "document_hash",
        chain_state.get("document_hash") or chain_state.get("doc_hash"),
        current_document.get("document_hash") or current_document.get("doc_hash"),
    )
    render_hash_compare(
        "merkle_root",
        chain_state.get("merkle_root") or chain_state.get("status_root"),
        current_document.get("merkle_root") or current_document.get("status_root"),
    )
    render_hash_compare(
        "version_hash",
        chain_state.get("version_hash") or chain_state.get("vh_latest"),
        current_document.get("version_hash") or current_document.get("vh_latest"),
    )

    st.subheader("最新历史版本 latest_version_record")
    render_json_block("latest_version_record", latest_version_record)

    if st.button("立即执行完整验证"):
        try:
            verify_result = api_verify(did)
            render_json_block("verify_result", verify_result)
            render_result_flag("整体有效性 is_valid", bool(verify_result.get("is_valid")))
        except Exception as exc:
            st.error(f"验证失败：{exc}")