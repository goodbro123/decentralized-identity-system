"""
健康检查路由模块

本模块提供系统运行状态探测接口，用于监控服务是否正常运行。
该接口通常被容器编排工具（如 Docker、Kubernetes）或前端健康检查调用。
"""

from flask import Blueprint

from shared.response import success


health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    """
    健康检查接口

    返回服务名称和运行状态，用于确认后端服务已正常启动并可对外提供服务。

    Returns:
        Response: 包含 success 标志和服务状态信息的 JSON 响应
    """
    return success(
        data={
            "service": "did-backend",
            "status": "running"
        },
        message="后端服务运行正常"
    )