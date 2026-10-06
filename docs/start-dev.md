# 日常启动说明

## 适用场景
本脚本用于日常开发，不清空链和数据库。

适合以下情况：
- 修改 Flask 后端 Python 代码
- 修改 Streamlit 页面
- 修改小程序前端
- 修改普通配置文件
- 只想让新代码生效

## 脚本文件
`start_dev.cmd`

## 执行效果
- 启动或重建容器
- 保留 `ganache_data`
- 保留 `mongo_data`
- 保留已部署合约
- 保留 Mongo 测试数据

## 不会做的事情
- 不会删除 Docker volume
- 不会清空本地区块链数据
- 不会清空 MongoDB 数据
- 不会删除 `deployments/address.json`

## 执行命令
```bat
start_dev.cmd