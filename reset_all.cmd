@echo off
chcp 65001 >nul
title DID Full Reset

echo ================================
echo 全量重置 DID Docker 环境
echo ================================

cd /d %~dp0

echo.
echo [1] 停止并删除容器、网络、数据卷
docker compose -f deploy/compose.yaml down -v

echo.
echo [2] 清理未使用的 Docker 资源
docker system prune -f

echo.
echo [3] 删除旧部署产物（避免旧地址和新链不一致）
if exist deployments\address.json del /f /q deployments\address.json
if exist deployments\deploy_metadata.json del /f /q deployments\deploy_metadata.json

echo.
echo [4] 如需彻底重置合约接口，请手动删除 abi.json
echo    如果你改了 Solidity 合约，请再执行：
echo    del /f /q deployments\abi.json

echo.
echo [5] 重新构建并启动环境
docker compose -f deploy/compose.yaml up -d --build

echo.
echo [6] 当前容器状态
docker compose -f deploy/compose.yaml ps

echo.
echo ================================
echo 全量重置完成
echo ================================
echo 接下来必须重新执行：
echo 1. docker exec -it did_backend sh
echo 2. python tests/test_rpc.py
echo 3. python scripts/compile_deploy.py
echo 4. python tests/test_contract.py
echo.

cmd