"""
Flask 应用入口模块

本模块是后端服务的启动入口，负责创建 Flask 应用实例，
注册所有蓝图路由，并配置运行参数。
"""

from flask import Flask

from api.routes.did_routes import did_bp
from api.routes.health_routes import health_bp


def create_app() -> Flask:
    """
    应用工厂函数

    创建并配置 Flask 应用实例，注册健康检查蓝图和 DID 业务蓝图。

    Returns:
        Flask: 已配置完成的 Flask 应用对象
    """
    app = Flask(__name__)

    # 注册健康检查蓝图，用于服务状态探测
    app.register_blueprint(health_bp)
    # 注册 DID 业务蓝图，提供去中心化身份管理接口
    app.register_blueprint(did_bp)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)