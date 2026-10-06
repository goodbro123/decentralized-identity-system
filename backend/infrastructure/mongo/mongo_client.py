"""
MongoDB 客户端模块

本模块负责管理 MongoDB 数据库连接，提供全局单例的 MongoClient 实例。
通过健康检查确保连接可用，并对外暴露数据库对象供仓储层使用。
"""

from pymongo import MongoClient

from shared.config import settings
from shared.exceptions import DatabaseConnectionError


_client: MongoClient | None = None


def get_mongo_client() -> MongoClient:
    """
    获取 MongoDB 客户端单例

    若客户端尚未初始化，则根据配置中的 `mongo_uri` 创建新连接，并执行 ping 命令验证连通性。
    连接失败时抛出 DatabaseConnectionError 异常。

    Returns:
        MongoClient: 已连接且可用的 MongoDB 客户端实例

    Raises:
        DatabaseConnectionError: 当无法连接到 MongoDB 服务器时抛出
    """
    global _client

    if _client is None:
        _client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000)

    try:
        _client.admin.command("ping")
    except Exception as e:
        raise DatabaseConnectionError(f"无法连接到 MongoDB：{e}") from e

    return _client


def get_database():
    """
    获取 MongoDB 数据库对象

    基于已连接的客户端和配置中的数据库名称，返回对应的 Database 实例，
    供各仓储模块进行集合操作。

    Returns:
        pymongo.database.Database: MongoDB 数据库对象
    """
    client = get_mongo_client()
    return client[settings.mongo_db_name]