"""
MongoDB 测试数据展示脚本

本脚本读取 `test_http_flow_visible.py` 生成的测试结果文件（默认为 `last_test_run.json`），
然后连接 MongoDB 数据库，依次查询并打印以下集合中与测试相关的文档：
- did_documents
- did_versions
- verification_records
- did_recovery_blocks
- experiment_records

通过该脚本，可以直观地核验 DID 注册、更新、验证、恢复等流程产生数据的完整性与正确性。
依赖：pymongo
运行：python tests/show_mongo_test_data.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from pprint import pprint

from pymongo import MongoClient

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'did_system')
SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_FILE = Path(os.getenv('TEST_OUTPUT_FILE', str(SCRIPT_DIR / 'last_test_run.json')))
MAX_DOCS = int(os.getenv('SHOW_MAX_DOCS', '10'))


EXPECTED_COLLECTIONS = [
    'did_documents',
    'did_versions',
    'verification_records',
    'did_recovery_blocks',
    'experiment_records',
]


def _load_last_run() -> dict:
    """
    读取上一轮测试运行输出的 JSON 结果文件。

    该文件由 `test_http_flow_visible.py` 生成，包含了测试所用的 DID、marker 以及接口返回数据。
    如果文件不存在，抛出 FileNotFoundError 并提示先运行 HTTP 测试脚本。

    Returns:
        dict: 解析后的测试结果字典

    Raises:
        FileNotFoundError: 当测试结果文件不存在时抛出
    """
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"找不到测试结果文件 {INPUT_FILE}。请先运行 test_http_flow_visible.py 生成数据。"
        )
    return json.loads(INPUT_FILE.read_text(encoding='utf-8'))


def _normalize(doc: dict) -> dict:
    """
    移除 MongoDB 文档中的 `_id` 字段，便于打印时保持简洁。

    Args:
        doc: 从 MongoDB 返回的原始文档

    Returns:
        dict: 去除 _id 后的文档副本
    """
    doc = dict(doc)
    doc.pop('_id', None)
    return doc


def main() -> int:
    """
    主函数：连接 MongoDB，根据测试 DID 或 marker 逐集合展示数据。

    返回 0 表示成功执行。
    """
    last_run = _load_last_run()
    did = last_run['did']
    marker = last_run['marker']

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    client.admin.command('ping')
    db = client[MONGO_DB_NAME]

    print(f'[信息] MONGO_URI={MONGO_URI}')
    print(f'[信息] MONGO_DB_NAME={MONGO_DB_NAME}')
    print(f'[信息] 测试 DID={did}')
    print(f'[信息] MongoDB 标识={marker}')

    for name in EXPECTED_COLLECTIONS:
        collection = db[name]
        print('\n' + '=' * 80)
        print(f'集合: {name}')

        query = {'did': did}
        if name == 'experiment_records':
            docs = list(collection.find({'did': did}, limit=MAX_DOCS))
        else:
            docs = list(collection.find(query, limit=MAX_DOCS))

        if not docs and name in ('did_documents', 'did_versions'):
            docs = list(collection.find({'document.profile.test_marker': marker}, limit=MAX_DOCS))

        if not docs:
            print('[空] 未找到与当前测试运行相关的文档')
            continue

        for index, doc in enumerate(docs, start=1):
            print(f'--- 文档 #{index} ---')
            pprint(_normalize(doc), sort_dicts=False)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())