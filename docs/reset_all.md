# 全量重置说明

## 适用场景
本脚本用于彻底重置 Docker 环境。

适合以下情况：
- 修改了 Solidity 合约
- 想清空链和数据库重新做实验
- Ganache 状态和部署地址不一致
- Mongo 数据已被污染
- 想恢复到全新环境

## 脚本文件
`reset_all.cmd`

## 执行效果
- 删除容器
- 删除网络
- 删除 volume
- 清空 Ganache 链数据
- 清空 MongoDB 数据
- 删除旧的部署地址文件和部署元数据

## 会删除什么
### Docker 卷
- `ganache_data`
- `mongo_data`

### 宿主机部署产物
- `deployments/address.json`
- `deployments/deploy_metadata.json`

## 可能还需要手动删除什么
如果你改了 Solidity 合约接口、事件或状态字段，还需要手动删除：

```text
deployments/abi.json