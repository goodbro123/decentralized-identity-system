"""
DID 注册

用于提交 DID 初始文档，并调用 Flask 的 /api/did/register 接口。
"""

from __future__ import annotations

import streamlit as st

from components.renderers import page_header, render_json_block
from services.data_service import api_register
from utils.validators import validate_did


page_header("DID 注册", "用于提交 DID 初始文档，并调用 Flask 的 /api/did/register 接口。")

with st.form("register_form"):
    did = st.text_input("DID", placeholder="例如：did:ethr:alice")
    name = st.text_input("姓名", placeholder="例如：Alice")
    public_key = st.text_input("公钥", placeholder="例如：pk_alice_demo")
    organization = st.text_input("组织", placeholder="例如：NJIT")
    email = st.text_input("邮箱", placeholder="例如：alice@example.com")
    role = st.text_input("角色", value="student")
    status = st.selectbox("状态", options=["active", "pending", "verified"], index=0)
    submitted = st.form_submit_button("提交注册", type="primary")

if submitted:
    try:
        did_value = validate_did(did)
        document = {
            "id": did_value,
            "name": name,
            "publicKey": public_key,
            "profile": {
                "organization": organization,
                "email": email,
            },
            "attributes": {
                "role": role,
                "status": status,
            },
        }
        result = api_register(did_value, document)
        st.success("DID 注册成功")
        render_json_block("register_result", result)
    except Exception as exc:
        st.error(f"注册失败：{exc}")