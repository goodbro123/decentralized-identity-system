"""
MongoDB 客户端管理模块（Streamlit 可视化平台）

本模块为 Streamlit 可视化平台提供与 MongoDB 的连接支持。
通过缓存机制创建并复用 MongoClient 实例和数据库对象，
便于各页面直接读取链下数据用于展示。
"""

from __future__ import annotations

import os

import streamlit as st
from pymongo import MongoClient


MONGO_URI = os.getenv("STREAMLIT_MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("STREAMLIT_MONGO_DB_NAME", "did_system")


@st.cache_resource(show_spinner=False)
def get_mongo_client() -> MongoClient:
    """
    获取全局唯一的 MongoDB 客户端实例（带缓存）。

    使用 `serverSelectionTimeoutMS` 超时设置，避免长时间等待。
    连接成功后执行 ping 命令验证连通性，若失败则底层会抛出异常。

    Returns:
        MongoClient: 已连接至 MongoDB 的客户端对象
    """
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    return client


@st.cache_resource(show_spinner=False)
def get_database():
    """
    获取 MongoDB 中当前业务数据库对象。

    通过缓存的客户端对象访问环境变量中指定的数据库名称。

    Returns:
        pymongo.database.Database: 可用于操作集合的数据库对象
    """
    return get_mongo_client()[MONGO_DB_NAME]