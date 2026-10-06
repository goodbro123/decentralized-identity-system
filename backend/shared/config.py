"""
系统配置模块

本模块定义了应用运行所需的所有配置项，所有配置均通过环境变量读取，

配置项采用不可变的 dataclass 实现，确保全局唯一且在运行时不会被意外修改。
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """
    系统配置类（不可变）

    所有配置字段均从环境变量中读取，若未设置则使用默认值。
    """

    flask_env: str = os.getenv("FLASK_ENV", "development")
  

    web3_provider: str = os.getenv("WEB3_PROVIDER", "http://ganache:8545")
    
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://mongo:27017/did_system")
   
    mongo_db_name: str = os.getenv("MONGO_DB_NAME", "did_system")
   
    chain_id: int = int(os.getenv("CHAIN_ID", "1337"))
   

    contract_abi_path: str = os.getenv("CONTRACT_ABI_PATH", "/deployments/abi.json")
    

    contract_address_path: str = os.getenv("CONTRACT_ADDRESS_PATH", "/deployments/address.json")
    

# 全局唯一配置实例，供其他模块导入使用
settings = Settings()
"""
全局配置单例对象。

项目中其他模块应通过 `from shared.config import settings` 导入该实例，以保证配置在整个应用生命周期内保持一致。
"""