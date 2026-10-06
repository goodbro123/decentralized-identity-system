"""
DID 管理 API 路由模块

本模块提供了面向去中心化身份（DID）的 RESTful 接口，包括：
- 身份认证挑战生成 (/api/did/auth/challenge)
- 查询最新状态 (/api/did/latest)
- 注册新 DID (/api/did/register)
- 更新 DID 文档 (/api/did/update)
- 完整性验证 (/api/did/verify)
- 属性默克尔证明 (/api/did/proof)
- 链下数据恢复 (/api/did/recover)
- 兼容旧测试接口 (/api/did/upsert)

所有接口均返回统一的 JSON 格式，便于前端（如微信小程序）解析和处理。
需要控制权证明的接口（register、update、recover）会先校验 auth 签名。
"""

from flask import Blueprint, request

from application.services.did_application_service import (
    build_attribute_proof_service,
    create_or_update_did_service,
    get_did_latest_service,
    recover_did_service,
    register_did_service,
    update_did_service,
    verify_did_service,
)
from application.services.did_auth_service import (
    create_auth_challenge,
    verify_did_auth,
)
from shared.exceptions import AppError, ValidationError
from shared.response import fail, success


did_bp = Blueprint("did", __name__, url_prefix="/api/did")


def _json_body() -> dict:
    """安全地从请求中解析 JSON 体，解析失败时返回空字典。"""
    return request.get_json(silent=True) or {}


def _normalize_recovery_method(force_method):
    """
    将前端传入的恢复方式别名转换为后端标准名称。

    标准名称：
        auto
        duplication
        erasure_code

    兼容旧名称：
        replica -> duplication
        erasure -> erasure_code

    注意：
        这里保留 auto，不直接转成 None。
        service 层会记录 requested_recovery_method = auto。
        codec 层再把 auto 转成 None 执行自动恢复。
    """
    if force_method in (None, ""):
        return "auto"

    method_map = {
        "auto": "auto",
        "duplication": "duplication",
        "replica": "duplication",
        "erasure_code": "erasure_code",
        "erasure": "erasure_code",
    }

    if force_method not in method_map:
        raise ValidationError(f"不支持的恢复方式：{force_method}")

    return method_map[force_method]

@did_bp.post("/auth/challenge")
def auth_challenge():
    """
    生成身份认证挑战接口。

    请求体 (JSON):
        did (str): DID 标识符。
        operation (str): 后续需要执行的操作类型。

    返回:
        JSON 响应，包含挑战原文、随机数 nonce 和时间戳等信息。
    """
    data = _json_body()
    did = data.get("did")
    operation = data.get("operation")

    if not did:
        return fail("缺少 did 参数", code=4001, status_code=400)
    if not operation:
        return fail("缺少 operation 参数", code=4002, status_code=400)

    try:
        return success(
            create_auth_challenge(did=did, operation=operation),
            "挑战创建成功",
        )
    except AppError as exc:
        return fail(exc.message, code=4003, status_code=400)
    except Exception as exc:
        return fail(str(exc), code=5000, status_code=500)


@did_bp.get("/latest")
def get_latest():
    """
    查询 DID 的最新状态（链上 + 链下）。

    请求参数 (Query String):
        did (str): 需要查询的 DID 标识符。

    返回:
        JSON 响应，包含链上状态、当前文档及最新版本记录。
    """
    did = request.args.get("did")
    if not did:
        return fail("缺少 did 参数", code=4001, status_code=400)

    try:
        return success(get_did_latest_service(did), "查询最新状态成功")
    except AppError as exc:
        return fail(exc.message, code=4002, status_code=400)
    except Exception as exc:
        return fail(str(exc), code=5000, status_code=500)


@did_bp.post("/bind")
def bind():
    data = _json_body()
    did = data.get("did")
    auth = data.get("auth")

    if not did:
        return fail("missing did", code=4001, status_code=400)

    try:
        auth_result = verify_did_auth(
            did=did,
            operation="bind",
            auth=auth,
            document=None,
        )

        latest = get_did_latest_service(did)

        return success(
            {
                "did": did,
                "auth_result": auth_result,
                "latest": latest,
            },
            "bind success",
        )
    except AppError as exc:
        return fail(exc.message, code=4002, status_code=400)
    except Exception as exc:
        return fail(str(exc), code=5000, status_code=500)


@did_bp.post("/register")
def register():
    """
    注册一个新的 DID。

    请求体 (JSON):
        did (str): 待注册的 DID 标识符。
        document (object): 初始 DID 文档内容。
        auth (object): 身份认证信息（包含签名后的挑战等）。

    返回:
        JSON 响应，包含注册结果、链上交易信息及认证结果。
    """
    data = _json_body()
    did = data.get("did")
    document = data.get("document")
    auth = data.get("auth")

    if not did:
        return fail("缺少 did 参数", code=4001, status_code=400)
    if not isinstance(document, dict):
        return fail("document 参数必须为对象", code=4003, status_code=400)

    try:
        auth_result = verify_did_auth(
            did=did,
            operation="register",
            auth=auth,
            document=document,
        )

        result = register_did_service(did=did, document=document)
        result["auth_result"] = auth_result

        return success(result, "注册成功")
    except AppError as exc:
        return fail(exc.message, code=4002, status_code=400)
    except Exception as exc:
        return fail(str(exc), code=5000, status_code=500)


@did_bp.post("/update")
def update():
    """
    更新一个已存在的 DID 文档。

    请求体 (JSON):
        did (str): DID 标识符。
        document (object): 新的 DID 文档内容。
        version (int, 可选): 指定新版本号，不传则自动递增。
        auth (object): 身份认证信息。

    返回:
        JSON 响应，包含更新后的版本号、各类哈希、变更属性及认证结果。
    """
    data = _json_body()
    did = data.get("did")
    document = data.get("document")
    version = data.get("version")
    auth = data.get("auth")

    if not did:
        return fail("缺少 did 参数", code=4001, status_code=400)
    if not isinstance(document, dict):
        return fail("document 参数必须为对象", code=4003, status_code=400)

    try:
        auth_result = verify_did_auth(
            did=did,
            operation="update",
            auth=auth,
            document=document,
        )

        result = update_did_service(
            did=did,
            document=document,
            version=int(version) if version is not None else None,
        )
        result["auth_result"] = auth_result

        return success(result, "更新成功")
    except AppError as exc:
        return fail(exc.message, code=4002, status_code=400)
    except Exception as exc:
        return fail(str(exc), code=5000, status_code=500)


@did_bp.post("/verify")
def verify():
    """
    对指定 DID 的文档进行完整性验证。

    请求体 (JSON):
        did (str): 待验证的 DID 标识符。
        version (int, 可选): 指定验证的版本号，不传则验证当前版本。

    返回:
        JSON 响应，包含各项哈希比对结果、版本连续性及交易验证状态。
    """
    data = _json_body()
    did = data.get("did")
    version = data.get("version")

    if not did:
        return fail("缺少 did 参数", code=4001, status_code=400)

    try:
        return success(
            verify_did_service(did=did, version=int(version) if version is not None else None),
            "验证成功",
        )
    except AppError as exc:
        return fail(exc.message, code=4002, status_code=400)
    except Exception as exc:
        return fail(str(exc), code=5000, status_code=500)


@did_bp.post("/proof")
def proof():
    """
    为指定属性路径生成默克尔包含证明。

    请求体 (JSON):
        did (str): DID 标识符。
        attribute_path (str): 需证明的属性路径，如 "profile.organization"。
        version (int, 可选): 文档版本号，不传则使用当前版本。

    返回:
        JSON 响应，包含默克尔证明路径及相关验证信息。
    """
    data = _json_body()
    did = data.get("did")
    attribute_path = data.get("attribute_path")
    version = data.get("version")

    if not did:
        return fail("缺少 did 参数", code=4001, status_code=400)
    if not attribute_path:
        return fail("缺少 attribute_path 参数", code=4004, status_code=400)

    try:
        return success(
            build_attribute_proof_service(
                did=did,
                attribute_path=attribute_path,
                version=int(version) if version is not None else None,
            ),
            "证明生成成功",
        )
    except AppError as exc:
        return fail(exc.message, code=4002, status_code=400)
    except Exception as exc:
        return fail(str(exc), code=5000, status_code=500)


@did_bp.post("/recover")
def recover():
    """
    从恢复块中重建 DID 文档。

    请求体 (JSON):
        did (str): 需要恢复的 DID 标识符。
        version (int, 可选): 目标恢复版本，不传则恢复至最新。
        force_method (str, 可选): 强制指定恢复方法 ("duplication" 或 "erasure_code")。
        missing_data_indexes (list[int], 可选): 模拟丢失的数据块索引（用于测试）。
        auth (object): 身份认证信息。

    返回:
        JSON 响应，包含恢复方法、完整性校验结果及认证结果。
    """
    data = _json_body()
    did = data.get("did")
    version = data.get("version")
    force_method = _normalize_recovery_method(data.get("force_method"))
    missing_data_indexes = data.get("missing_data_indexes", [])
    auth = data.get("auth")

    if not did:
        return fail("缺少 did 参数", code=4001, status_code=400)
    if not isinstance(missing_data_indexes, list):
        return fail("missing_data_indexes 参数必须为列表", code=4005, status_code=400)

    try:
        auth_result = verify_did_auth(
            did=did,
            operation="recover",
            auth=auth,
            document=None,
        )

        result = recover_did_service(
            did=did,
            version=int(version) if version is not None else None,
            force_method=force_method,
            missing_data_indexes=missing_data_indexes,
        )
        result["auth_result"] = auth_result

        return success(result, "恢复成功")
    except AppError as exc:
        return fail(exc.message, code=4002, status_code=400)
    except Exception as exc:
        return fail(str(exc), code=5000, status_code=500)


@did_bp.post("/upsert")
def upsert():
    """
    创建或更新 DID 文档的统一入口（兼容旧测试脚本）。

    注意：
        正式的小程序前端不应使用此接口，请使用 /api/did/register 和 /api/did/update，
        并配合 /api/did/auth/challenge 完成身份认证。

    请求体 (JSON):
        did (str): DID 标识符。
        version (int): 版本号，首次注册须为 1，后续更新须递增。
        document (object): DID 文档内容。

    返回:
        JSON 响应，根据 DID 是否存在自动执行注册或更新操作。
    """
    data = _json_body()
    did = data.get("did")
    version = data.get("version")
    document = data.get("document")

    if not did:
        return fail("缺少 did 参数", code=4001, status_code=400)
    if version is None:
        return fail("缺少 version 参数", code=4006, status_code=400)
    if not isinstance(document, dict):
        return fail("document 参数必须为对象", code=4003, status_code=400)

    try:
        return success(
            create_or_update_did_service(
                did=did,
                version=int(version),
                document=document,
            ),
            "操作成功",
        )
    except AppError as exc:
        return fail(exc.message, code=4002, status_code=400)
    except Exception as exc:
        return fail(str(exc), code=5000, status_code=500)