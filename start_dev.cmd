@echo off
chcp 65001 >nul

echo ================================
echo 启动 DID Docker 环境
echo ================================

cd /d %~dp0



echo.
echo [1] 启动容器（保留链和数据库数据）
docker compose -f deploy/compose.yaml up -d --build

echo.
echo [2] 当前容器状态
docker compose -f deploy/compose.yaml ps

echo.
echo ================================
echo 日常启动完成
echo ================================
echo.
echo 常用命令：
echo.
echo 1. 进入后端容器：
echo    docker exec -it did_backend sh
echo.
echo 2. 在容器里测试链连接：
echo    python tests/test_rpc.py
echo.
echo 3. 部署合约：
echo    python scripts/compile_deploy.py
echo.
echo 4. 测试合约：
echo    python tests/test_contract.py
echo.
echo 5. 测试后端接口：
echo    python tests/test_http_flow_visible.py
echo.
echo 6. 查看 Mongo 测试数据：
echo    python tests/show_mongo_test_data.py
echo.
echo 7. 查看 Streamlit：
echo    http://localhost:8501
echo.

cmd /k