"""
智能合约编译与部署脚本

本脚本提供了从 Solidity 源码到链上合约部署的端到端自动化流程。主要功能包括：
1. 读取合约源文件（默认为 DIDState.sol），自动识别 Solidity 版本。
2. 通过 py-solc-x 或系统 solc 命令行工具编译合约，生成 ABI 和字节码。
3. 连接以太坊网络（默认为 Ganache 本地测试网络），使用解锁账户部署合约。
4. 将编译产物（ABI、合约地址、详细部署元数据）保存为 JSON 文件，供后端服务加载。

支持通过环境变量灵活配置：
- CONTRACT_SOURCE_PATH：合约源文件路径
- CONTRACT_NAME：指定编译的合约名称（适用于多合约文件）
- SOLIDITY_VERSION：强制指定编译器版本
- DEPLOYER_ACCOUNT：指定部署账户地址
- WEB3_PROVIDER / CHAIN_ID / CONTRACT_ABI_PATH / CONTRACT_ADDRESS_PATH 等配置项
  优先从 shared.config 模块导入，否则回退到环境变量。

典型用法（在 Docker 容器内）：
    docker exec -it -w /app did_backend python scripts/compile_deploy.py

注意事项：
- 若容器中未安装 solc 或 py-solc-x，脚本会尝试自动安装 py-solc-x 并下载对应版本编译器。
- 部署前确保 Ganache 已启动且 RPC 可访问；确保部署账户有足够余额（本地测试网无需关注）。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
# 当前脚本位于 backend/scripts/compile_deploy.py
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

# 将 backend 目录加入 Python 搜索路径，以便导入 shared.config 等模块
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_settings() -> dict[str, Any]:
    """
    加载部署所需的核心配置参数。

    优先尝试从项目已有的 shared.config 模块中读取 Settings 对象，
    该对象包含 Web3 提供者地址、链 ID、ABI 路径、合约地址路径等配置。
    如果导入失败（例如模块尚未初始化），则回退到从环境变量中读取，
    确保在任何环境下脚本均能运行。

    Returns:
        dict: 包含以下键值的字典
            - web3_provider (str): 以太坊节点 RPC 地址，如 "http://ganache:8545"
            - chain_id (int): 链 ID，本地测试网通常为 1337
            - contract_abi_path (str): ABI 文件的输出路径
            - contract_address_path (str): 合约地址文件的输出路径
    """
    try:
        from shared.config import settings  # type: ignore

        return {
            "web3_provider": getattr(
                settings, "web3_provider", os.getenv("WEB3_PROVIDER", "http://ganache:8545")
            ),
            "chain_id": int(
                getattr(settings, "chain_id", int(os.getenv("CHAIN_ID", "1337")))
            ),
            "contract_abi_path": getattr(
                settings,
                "contract_abi_path",
                os.getenv("CONTRACT_ABI_PATH", "/deployments/abi.json"),
            ),
            "contract_address_path": getattr(
                settings,
                "contract_address_path",
                os.getenv("CONTRACT_ADDRESS_PATH", "/deployments/address.json"),
            ),
        }
    except Exception:
        return {
            "web3_provider": os.getenv("WEB3_PROVIDER", "http://ganache:8545"),
            "chain_id": int(os.getenv("CHAIN_ID", "1337")),
            "contract_abi_path": os.getenv("CONTRACT_ABI_PATH", "/deployments/abi.json"),
            "contract_address_path": os.getenv("CONTRACT_ADDRESS_PATH", "/deployments/address.json"),
        }


SETTINGS = _load_settings()


def _resolve_output_path(raw_path: str) -> Path:
    """
    将配置中可能为相对路径的输出路径转换为基于项目根目录的绝对路径。

    这样无论脚本从哪个目录执行，产物都会输出到正确的位置。
    如果 `raw_path` 已经是绝对路径，则直接返回。

    Args:
        raw_path: 原始路径字符串（绝对或相对）

    Returns:
        Path: 解析后的绝对路径对象
    """
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


# 合约源文件路径：优先使用环境变量，否则使用默认路径
DEFAULT_CONTRACT_SOURCE = BACKEND_DIR / "contracts" / "DIDState.sol"
CONTRACT_SOURCE_PATH = Path(
    os.getenv("CONTRACT_SOURCE_PATH", str(DEFAULT_CONTRACT_SOURCE))
).resolve()
# 目标合约名称（若文件包含多个合约），由环境变量指定
TARGET_CONTRACT_NAME = os.getenv("CONTRACT_NAME")
# Solidity 编译器版本，若未指定则从 pragma 解析
SOLIDITY_VERSION = os.getenv("SOLIDITY_VERSION")
# 部署产物的输出路径
ABI_OUTPUT_PATH = _resolve_output_path(str(SETTINGS["contract_abi_path"]))
ADDRESS_OUTPUT_PATH = _resolve_output_path(str(SETTINGS["contract_address_path"]))
# 额外保存一份包含全部部署细节的元数据文件，便于审计
METADATA_OUTPUT_PATH = ADDRESS_OUTPUT_PATH.with_name("deploy_metadata.json")
# 部署账户，若未指定则使用节点的第一个解锁账户
DEPLOYER_ACCOUNT = os.getenv("DEPLOYER_ACCOUNT")


class DeployError(Exception):
    """
    部署流程中的自定义异常类。

    用于包装所有在编译或部署过程中可能出现的可预期错误，例如：
    - 合约源文件不存在
    - 编译器未安装
    - 编译失败
    - 无法连接区块链节点
    - 部署交易失败
    上层代码可以捕获该异常并给出友好提示。
    """
    pass


def _read_source(path: Path) -> str:
    """
    读取合约源代码文件的内容。

    前置条件：path 必须存在。
    若文件不存在，抛出 DeployError 并明确提示文件路径。

    Args:
        path: 合约源文件的路径

    Returns:
        str: 文件的 UTF-8 文本内容
    """
    if not path.exists():
        raise DeployError(f"合约文件不存在：{path}")
    return path.read_text(encoding="utf-8")


def _detect_solidity_version(source: str) -> str:
    """
    从 Solidity 源代码中提取编译器版本。

    优先级：
    1. 环境变量 SOLIDITY_VERSION（允许覆盖）
    2. 从 pragma 声明中正则匹配版本号，例如 `pragma solidity ^0.8.20;`
    3. 默认版本 "0.8.20"

    Args:
        source: Solidity 源码字符串

    Returns:
        str: 确定的编译器版本，如 "0.8.20"
    """
    if SOLIDITY_VERSION:
        return SOLIDITY_VERSION

    match = re.search(r"pragma\s+solidity\s+\^?(\d+\.\d+\.\d+)\s*;", source)
    if match:
        return match.group(1)

    return "0.8.20"


def _select_contract_name(compiled_names: list[str], source_path: Path) -> str:
    """
    从编译得到的合约名称列表中选择要部署的目标合约。

    选择逻辑：
    1. 若环境变量 CONTRACT_NAME 已设置且包含在列表中，直接使用。
    2. 否则，优先选择与源文件主名（不含扩展名）相同的合约。
    3. 若仍找不到，使用列表中的最后一个合约名称（通常适用于单合约文件）。

    若 CONTRACT_NAME 指定了不存在的名称，抛出 DeployError 并列出可用合约。

    Args:
        compiled_names: 编译成功的合约名称列表
        source_path: 合约源文件路径，用于提取默认主名

    Returns:
        str: 最终决定部署的合约名称
    """
    if TARGET_CONTRACT_NAME:
        if TARGET_CONTRACT_NAME not in compiled_names:
            raise DeployError(
                f"环境变量 CONTRACT_NAME 指定了未编译到的合约：{TARGET_CONTRACT_NAME}，"
                f"可用合约列表：{compiled_names}"
            )
        return TARGET_CONTRACT_NAME

    preferred = source_path.stem
    if preferred in compiled_names:
        return preferred

    return compiled_names[-1]


def _compile_with_solcx(
    source_path: Path, source_code: str, solc_version: str
) -> tuple[str, list[Any], str]:
    """
    使用 py-solc-x Python 库编译 Solidity 合约。

    该方法会自动安装所需版本的 solc 编译器，然后调用标准 JSON 接口进行编译。
    编译选项开启了优化器（200 runs）并只输出 ABI 和字节码。

    Args:
        source_path: 源文件路径
        source_code: 源码内容
        solc_version: 编译器版本，如 "0.8.20"

    Returns:
        tuple: (合约名称, ABI 列表, 字节码十六进制字符串)

    Raises:
        DeployError: 当 py-solc-x 未安装、编译失败或字节码为空时抛出
    """
    try:
        from solcx import (
            compile_standard,
            get_installed_solc_versions,
            install_solc,
            set_solc_version,
        )
    except Exception as exc:
        raise DeployError(f"py-solc-x 未安装，无法使用 solcx 编译：{exc}") from exc

    # 确保目标版本已安装并设置为当前版本
    installed = {str(v) for v in get_installed_solc_versions()}
    if solc_version not in installed:
        install_solc(solc_version)
    set_solc_version(solc_version)

    standard_input = {
        "language": "Solidity",
        "sources": {source_path.name: {"content": source_code}},
        "settings": {
            "optimizer": {"enabled": True, "runs": 200},
            "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}},
        },
    }

    compiled = compile_standard(standard_input)
    contracts = compiled.get("contracts", {}).get(source_path.name, {})
    if not contracts:
        raise DeployError(f"编译结果中未找到合约：{source_path.name}")

    contract_name = _select_contract_name(list(contracts.keys()), source_path)
    artifact = contracts[contract_name]
    abi = artifact["abi"]
    bytecode = artifact["evm"]["bytecode"]["object"]
    if not bytecode:
        raise DeployError(f"编译后的合约字节码为空：{contract_name}")

    return contract_name, abi, bytecode


def _compile_with_solc_cli(
    source_path: Path, source_code: str, solc_version: str
) -> tuple[str, list[Any], str]:
    """
    使用系统安装的 solc 命令行工具编译合约。

    该函数作为 py-solc-x 不可用时的备用方案。
    它调用 `solc --optimize --combined-json abi,bin <file>` 并解析输出。
    注意：忽略传入的 solc_version 和 source_code，因为命令行工具会自行处理。

    Args:
        source_path: 源文件路径
        source_code: 源码内容（未使用）
        solc_version: 版本字符串（未使用）

    Returns:
        tuple: (合约名称, ABI 列表, 字节码十六进制字符串)

    Raises:
        DeployError: 当 solc 命令不可用、编译返回非零或字节码为空时抛出
    """
    _ = source_code, solc_version  # 显式忽略未用参数

    solc_bin = shutil.which("solc")
    if not solc_bin:
        raise DeployError("系统中未找到 solc 命令行工具，请先安装 solc")

    cmd = [solc_bin, "--optimize", "--combined-json", "abi,bin", str(source_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise DeployError(
            result.stderr.strip() or result.stdout.strip() or "solc 编译失败，请检查合约语法"
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise DeployError(f"无法解析 solc 输出：{exc}") from exc

    contracts = payload.get("contracts", {})
    if not contracts:
        raise DeployError("solc 编译结果中未包含任何合约")

    # 从 combined-json 的键中提取纯合约名（格式：file:Contract）
    contract_names: list[str] = []
    by_name: dict[str, dict[str, Any]] = {}
    for key, value in contracts.items():
        contract_name = key.split(":")[-1]
        contract_names.append(contract_name)
        by_name[contract_name] = value

    selected_name = _select_contract_name(contract_names, source_path)
    artifact = by_name[selected_name]

    abi_raw = artifact.get("abi")
    abi = json.loads(abi_raw) if isinstance(abi_raw, str) else abi_raw
    bytecode = artifact.get("bin")
    if not bytecode:
        raise DeployError(f"编译后的合约字节码为空：{selected_name}")

    return selected_name, abi, bytecode


def compile_contract() -> tuple[str, list[Any], str, str]:
    """
    尝试使用 solcx 和 solc CLI 两种方式编译合约，只要有任一成功即返回。

    如果两种方式均失败，汇总错误信息并抛出 DeployError。

    Returns:
        tuple: (合约名称, ABI 列表, bytecode 字符串, 实际使用的 Solidity 版本)

    Raises:
        DeployError: 当所有编译尝试都失败时抛出，并包含具体错误详情
    """
    source_code = _read_source(CONTRACT_SOURCE_PATH)
    solc_version = _detect_solidity_version(source_code)

    errors: list[str] = []
    for compiler in (_compile_with_solcx, _compile_with_solc_cli):
        try:
            contract_name, abi, bytecode = compiler(
                CONTRACT_SOURCE_PATH, source_code, solc_version
            )
            return contract_name, abi, bytecode, solc_version
        except Exception as exc:
            errors.append(f"{compiler.__name__}: {exc}")

    raise DeployError(
        "合约编译失败，请先安装 py-solc-x 或 solc 命令行工具。详细错误： " + " | ".join(errors)
    )


def _get_web3():
    """
    初始化并返回连接至以太坊节点的 Web3 实例。

    使用配置中的 web3_provider 地址创建 HTTPProvider，
    并检查连接是否成功。若 web3.py 未安装或无法连接，抛出 DeployError。

    Returns:
        Web3: 已连接的 Web3 实例
    """
    try:
        from web3 import Web3
    except Exception as exc:
        raise DeployError("web3.py 未安装，请执行 pip install web3") from exc

    provider_url = str(SETTINGS["web3_provider"])
    w3 = Web3(Web3.HTTPProvider(provider_url))
    if not w3.is_connected():
        raise DeployError(f"无法连接到区块链节点：{provider_url}")
    return w3


def deploy_contract(
    contract_name: str, abi: list[Any], bytecode: str
) -> dict[str, Any]:
    """
    将编译好的合约部署到区块链网络。

    执行步骤：
    1. 获取 Web3 连接和可用的解锁账户列表。
    2. 选定部署账户（环境变量或第一个账户）。
    3. 构造合约对象并发送部署交易。
    4. 等待交易回执并提取合约地址。
    5. 返回包含部署详情的字典。

    Args:
        contract_name: 合约名称
        abi: 合约 ABI 列表
        bytecode: 编译后的字节码（可带或不带 0x 前缀）

    Returns:
        dict: 部署信息字典，包括合约名称、地址、交易哈希、区块号、
              状态、Gas 消耗、部署账户和链 ID。

    Raises:
        DeployError: 当无可用账户、指定账户无效、交易回执无合约地址时抛出
    """
    w3 = _get_web3()

    accounts = w3.eth.accounts
    if not accounts:
        raise DeployError("节点未提供任何已解锁的账户，请检查 Ganache 配置")

    sender = DEPLOYER_ACCOUNT or accounts[0]
    if sender not in accounts:
        raise DeployError(f"指定的部署账户不在已解锁账户列表中：{sender}")

    # 确保 bytecode 以 0x 开头
    contract = w3.eth.contract(
        abi=abi,
        bytecode=(bytecode if bytecode.startswith("0x") else f"0x{bytecode}"),
    )

    tx_hash = contract.constructor().transact({"from": sender})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt.contractAddress is None:
        raise DeployError("部署交易回执中未包含合约地址，部署可能失败")

    return {
        "contract_name": contract_name,
        "contract_address": w3.to_checksum_address(receipt.contractAddress),
        "tx_hash": tx_hash.hex(),
        "block_number": int(receipt.blockNumber),
        "status": int(receipt.status),
        "gas_used": int(receipt.gasUsed),
        "deployer": sender,
        "chain_id": int(w3.eth.chain_id),
    }


def save_artifacts(
    contract_name: str,
    abi: list[Any],
    deploy_info: dict[str, Any],
    solc_version: str,
) -> None:
    """
    将编译部署的产物保存到磁盘。

    输出文件包括：
    - ABI 文件（abi.json）
    - 合约地址文件（address.json），仅包含合约地址和名称
    - 元数据文件（deploy_metadata.json），记录完整部署信息，便于审计

    所有父目录若不存在会自动创建。

    Args:
        contract_name: 合约名称
        abi: 合约 ABI
        deploy_info: deploy_contract 返回的部署信息字典
        solc_version: 使用的编译器版本
    """
    ABI_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ADDRESS_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    METADATA_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    ABI_OUTPUT_PATH.write_text(
        json.dumps(abi, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    ADDRESS_OUTPUT_PATH.write_text(
        json.dumps(
            {
                "contractAddress": deploy_info["contract_address"],
                "contractName": contract_name,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    metadata = {
        "contractName": contract_name,
        "contractSourcePath": str(CONTRACT_SOURCE_PATH),
        "solidityVersion": solc_version,
        "provider": str(SETTINGS["web3_provider"]),
        "chainId": int(deploy_info["chain_id"]),
        "contractAddress": deploy_info["contract_address"],
        "transactionHash": deploy_info["tx_hash"],
        "blockNumber": int(deploy_info["block_number"]),
        "status": int(deploy_info["status"]),
        "gasUsed": int(deploy_info["gas_used"]),
        "deployer": deploy_info["deployer"],
        "abiPath": str(ABI_OUTPUT_PATH),
        "addressPath": str(ADDRESS_OUTPUT_PATH),
    }
    METADATA_OUTPUT_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    """
    脚本主入口：串行执行合约编译、部署和产物保存。

    输出关键配置路径，然后依次调用 compile_contract、deploy_contract、
    检查交易状态（status 必须为 1），最后保存文件。
    任何步骤失败均抛出 DeployError 并终止执行。
    """
    print("=== compile_deploy.py ===")
    print(f"合约源文件        : {CONTRACT_SOURCE_PATH}")
    print(f"RPC 提供者        : {SETTINGS['web3_provider']}")
    print(f"ABI 输出路径      : {ABI_OUTPUT_PATH}")
    print(f"地址输出路径      : {ADDRESS_OUTPUT_PATH}")

    contract_name, abi, bytecode, solc_version = compile_contract()
    print(f"编译后的合约名称  : {contract_name}")
    print(f"Solidity 版本     : {solc_version}")
    print(f"ABI 条目数量      : {len(abi)}")
    print(f"字节码长度        : {len(bytecode)}")

    deploy_info = deploy_contract(contract_name, abi, bytecode)
    if int(deploy_info["status"]) != 1:
        raise DeployError(f"部署交易失败，交易回执信息：{deploy_info}")

    save_artifacts(contract_name, abi, deploy_info, solc_version)

    print("--- 部署成功 ---")
    print(f"合约名称          : {contract_name}")
    print(f"合约地址          : {deploy_info['contract_address']}")
    print(f"交易哈希          : {deploy_info['tx_hash']}")
    print(f"区块号            : {deploy_info['block_number']}")
    print(f"Gas 消耗          : {deploy_info['gas_used']}")
    print(f"元数据文件路径    : {METADATA_OUTPUT_PATH}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[compile_deploy.py] 错误：{exc}")
        raise