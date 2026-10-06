"""
统一响应格式模块

本模块提供 Flask API 层统一的标准 JSON 响应格式。
所有接口均通过 `success()` 和 `fail()` 函数返回结构一致的响应体，
便于前端（如微信小程序）统一处理业务状态与错误信息。
"""

from flask import jsonify


def success(data=None, message: str = "操作成功", status_code: int = 200):
    """
    成功响应构造器

    返回一个标准的成功 JSON 响应，包含 `success: true` 标志、提示消息及业务数据。

    Args:
        data: 响应中携带的业务数据，可为字典、列表、字符串或 None
        message: 成功提示消息，默认为 "操作成功"
        status_code: HTTP 状态码，默认为 200

    Returns:
        Flask Response 对象，Content-Type 为 application/json
    """
    return jsonify({
        "success": True,
        "message": message,
        "data": data
    }), status_code


def fail(message: str = "操作失败", status_code: int = 400, data=None):
    """
    失败响应构造器

    返回一个标准的失败 JSON 响应，包含 `success: false` 标志、错误消息及附加数据。

    Args:
        message: 错误描述消息，默认为 "操作失败"
        status_code: HTTP 状态码，默认为 400（Bad Request）
        data: 附加的错误详情数据，如字段校验失败列表等

    Returns:
        Flask Response 对象，Content-Type 为 application/json
    """
    return jsonify({
        "success": False,
        "message": message,
        "data": data
    }), status_code