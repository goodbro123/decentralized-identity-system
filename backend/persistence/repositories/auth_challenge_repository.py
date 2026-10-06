"""
身份验证挑战（Auth Challenge）持久化模块

本模块负责 `auth_challenges` 集合的持久化操作，用于存储 DID 控制权验证过程中
生成的挑战（challenge）。每次敏感操作前都会生成一次性的 nonce 与挑战信息，
并在使用后标记为已用，以防止重放攻击。
"""

from datetime import datetime, timedelta, timezone

from infrastructure.mongo.mongo_client import get_database


COLLECTION_NAME = "auth_challenges"


def save_auth_challenge(
    did: str,
    operation: str,
    nonce: str,
    challenge: str,
    timestamp: int,
    expires_in: int = 300,
) -> dict:
    """
    保存一条身份验证挑战记录。

    该记录在 DID 控制权校验开始时创建，包含一次性 nonce、挑战内容、操作类型和过期时间。
    初始状态为未被使用（used=False）。

    Args:
        did: 需要进行控制权验证的 DID 标识符。
        operation: 关联的操作类型，如 "update"、"delete"。
        nonce: 随机数（一次性令牌），用于绑定本次挑战。
        challenge: 服务端生成的需要签名的挑战字符串。
        timestamp: 客户端发起请求时的 Unix 时间戳（秒）。
        expires_in: 挑战的有效期（秒），默认 300 秒。

    Returns:
        dict: 成功保存后的挑战记录副本（不含 _id 字段）。
    """
    db = get_database()
    collection = db[COLLECTION_NAME]

    now = datetime.utcnow()
    data = {
        "did": did,
        "operation": operation,
        "nonce": nonce,
        "challenge": challenge,
        "timestamp": int(timestamp),
        "expires_at": now + timedelta(seconds=expires_in),
        "used": False,
        "created_at": now,
        "updated_at": now,
    }

    collection.insert_one(data)
    data.pop("_id", None)
    return data


def get_auth_challenge(did: str, operation: str, nonce: str) -> dict | None:
    """
    根据 DID、操作类型和 nonce 查询身份验证挑战记录。

    用于在用户发回签名后检索对应的挑战信息，以便校验签名是否正确且未过期。

    Args:
        did: DID 标识符。
        operation: 关联的操作类型。
        nonce: 本次挑战的随机数。

    Returns:
        dict 或 None: 匹配的挑战记录（不含 _id），若未找到则返回 None。
    """
    db = get_database()
    collection = db[COLLECTION_NAME]

    return collection.find_one(
        {
            "did": did,
            "operation": operation,
            "nonce": nonce,
        },
        {"_id": 0},
    )


def mark_auth_challenge_used(did: str, operation: str, nonce: str) -> None:
    """
    将指定的身份验证挑战记录标记为已使用。

    每次挑战只能使用一次，调用此方法后该 nonce 将失效，防止重放攻击。
    同时更新 `updated_at` 时间戳。

    Args:
        did: DID 标识符。
        operation: 关联的操作类型。
        nonce: 本次挑战的随机数。
    """
    db = get_database()
    collection = db[COLLECTION_NAME]

    collection.update_one(
        {
            "did": did,
            "operation": operation,
            "nonce": nonce,
        },
        {
            "$set": {
                "used": True,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )