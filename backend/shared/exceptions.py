"""
系统自定义异常模块

本模块定义了应用中各层可能抛出的业务异常类，均继承自统一的 `AppError` 基类。
使用自定义异常有助于：
1. 在 API 层精确捕获特定错误类型并返回恰当的 HTTP 状态码；
2. 避免向客户端暴露内部异常的敏感堆栈信息；
3. 保持代码可读性与可维护性。

所有异常类均提供默认的中文错误消息，并允许在实例化时覆盖。
"""


class AppError(Exception):
    """
    应用异常基类

    所有自定义业务异常均应继承此类。
    提供默认的中文错误消息，并允许在实例化时覆盖。

    Attributes:
        message: 异常的错误消息文本
    """

    default_message = "应用程序内部错误"

    def __init__(self, message: str | None = None):
        """
        初始化异常实例

        Args:
            message: 可选的自定义错误消息，若不提供则使用类的默认消息
        """
        super().__init__(message or self.default_message)
        self.message = message or self.default_message


class BlockchainConnectionError(AppError):
    """
    区块链连接异常

    当无法连接到 Ganache 或其他以太坊节点（RPC 不可达、网络超时等）时抛出。
    """

    default_message = "区块链节点连接失败"


class ContractLoadError(AppError):
    """
    合约加载异常

    当智能合约 ABI 文件或部署地址文件缺失、格式错误或无法解析时抛出。
    """

    default_message = "智能合约加载失败"


class DatabaseConnectionError(AppError):
    """
    数据库连接异常

    当 MongoDB 连接失败（服务未启动、认证错误、网络不通等）时抛出。
    """

    default_message = "MongoDB 数据库连接失败"


class ValidationError(AppError):
    """
    数据校验异常

    当请求参数不符合预期格式或业务规则时抛出。
    通常用于 API 层参数校验或领域对象构造时的合法性检查。
    """

    default_message = "数据校验未通过"


class VersionRuleError(AppError):
    """
    版本规则违反异常

    当 DID 文档更新操作中的版本号不满足递增规则时抛出。
    用于保证链下文档版本管理的合法性与可追溯性。
    """

    default_message = "版本号规则不满足"


class NotFoundError(AppError):
    """
    资源未找到异常

    当请求的 DID、文档或版本记录在数据库或链上不存在时抛出。
    """

    default_message = "找不到指定的资源"


class VerificationError(AppError):
    """
    身份验证或数据校验异常

    当链上与链下数据不一致、哈希不匹配或版本连续性校验失败时抛出。
    """

    default_message = "身份或数据验证失败"


class RecoveryError(AppError):
    """
    数据恢复异常

    当链下数据恢复块缺失、恢复后完整性校验不通过时抛出。
    """

    default_message = "数据恢复失败"


class AuthError(AppError):
    """
    DID 控制器身份验证异常

    当调用者无法证明其拥有指定 DID 的控制权（如签名验证失败）时抛出。
    """

    default_message = "DID 控制器身份验证失败"