"""
版本规则校验模块

本模块定义 DID 文档更新操作必须遵守的业务规则，包括：
- 版本号递增规则（首次注册必须为 1，后续更新必须严格递增 1）
- 文档内容变更校验（禁止无实际变化的更新）

所有规则函数在条件不满足时抛出 VersionRuleError 异常，
由上层服务捕获并转换为友好的错误提示。
"""

from shared.exceptions import VersionRuleError


def ensure_initial_or_incremental_version(
    previous_version: int | None,
    new_version: int,
) -> None:
    """
    校验版本号是否符合首次注册或严格递增规则

    根据是否存在历史版本执行不同校验：
    - 若为首次注册（previous_version 为 None），要求新版本号必须为 1。
    - 若为更新操作（previous_version 已存在），要求新版本号必须等于前一个版本号 + 1。

    Args:
        previous_version: 历史最新版本号，首次注册时为 None
        new_version: 拟更新的版本号

    Raises:
        VersionRuleError: 当版本号不满足规则时抛出

    Examples:
        >>> ensure_initial_or_incremental_version(None, 1)    # 通过
        >>> ensure_initial_or_incremental_version(3, 4)      # 通过
        >>> ensure_initial_or_incremental_version(None, 2)    # 抛出异常
        >>> ensure_initial_or_incremental_version(3, 5)      # 抛出异常
    """
    if previous_version is None:
        if int(new_version) != 1:
            raise VersionRuleError("首次注册时版本号必须为 1")
        return

    if int(new_version) != int(previous_version) + 1:
        raise VersionRuleError(
            f"新版本号必须等于前一版本号加 1："
            f"前一版本={previous_version}，新版本={new_version}"
        )


def ensure_document_changed(changed_attributes: list[dict]) -> None:
    """
    校验 DID 文档更新是否存在实际的属性变更

    若变更属性列表为空，说明新旧文档完全一致，此时抛出异常以阻止无意义的链上交易。

    Args:
        changed_attributes: 由 compute_changed_attributes 返回的变更属性列表

    Raises:
        VersionRuleError: 当没有任何属性发生变更时抛出
    """
    if not changed_attributes:
        raise VersionRuleError("文档未发生任何属性变更，无需更新")