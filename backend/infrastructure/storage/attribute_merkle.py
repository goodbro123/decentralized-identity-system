"""
属性级默克尔树模块

本模块提供了基于文档属性路径构建默克尔树（Merkle Tree）的功能，
并支持生成和验证属性的包含证明。主要用于实现 DID 文档字段级别的
完整性验证与选择性披露。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from infrastructure.crypto.hash_service import combine_hashes, keccak_text
from infrastructure.storage.canonical_json import to_canonical_json


@dataclass(frozen=True)
class MerkleLeaf:
    """
    默克尔树的叶子节点

    表示 DID 文档扁平化后的一个属性，包含其路径、原始值、
    规范化 JSON 编码以及该叶子的 Keccak-256 哈希值。

    Attributes:
        path: 属性在文档中的完整路径，如 "credentialSubject.name"
        value: 属性的原始值
        encoded: 经规范化 JSON 序列化后的字符串
        leaf_hash: 叶子的 Keccak-256 哈希（十六进制）
    """
    path: str
    value: Any
    encoded: str
    leaf_hash: str


def flatten_document(data: Any, parent_key: str = "") -> list[tuple[str, Any]]:
    """
    将嵌套的 DID 文档扁平化为路径-值对列表

    遍历 JSON 对象，对字典键按字母排序以保证确定性，对数组使用下标索引。
    最终返回的路径可用于构建默克尔树的叶子节点。

    Args:
        data: 待扁平化的文档（dict、list 或基本类型）
        parent_key: 上级路径前缀，用于递归拼接

    Returns:
        list[tuple[str, Any]]: 由 (属性路径, 属性值) 组成的列表
    """
    items: list[tuple[str, Any]] = []

    if isinstance(data, dict):
        for key in sorted(data.keys()):
            new_key = f"{parent_key}.{key}" if parent_key else key
            items.extend(flatten_document(data[key], new_key))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            new_key = f"{parent_key}[{index}]"
            items.extend(flatten_document(value, new_key))
    else:
        items.append((parent_key, data))

    return items


class AttributeMerkleTree:
    """
    属性级默克尔树

    根据 DID 文档的扁平化属性列表构建默克尔树，提供根哈希计算、
    指定属性的包含证明生成等功能。树采用 Keccak-256 哈希算法，
    通过两两组合节点直至得到唯一根哈希。
    """

    def __init__(self, leaves: list[MerkleLeaf]):
        """
        初始化默克尔树

        若叶子列表为空，则自动创建一个占位叶子以保证树结构完整。

        Args:
            leaves: 由扁平化文档生成的叶子节点列表
        """
        if not leaves:
            encoded = to_canonical_json({"path": "", "value": None})
            leaves = [MerkleLeaf(path="", value=None, encoded=encoded, leaf_hash=keccak_text(encoded))]

        self.leaves = leaves
        self._path_to_index = {leaf.path: idx for idx, leaf in enumerate(self.leaves)}
        self.levels = self._build_levels([leaf.leaf_hash for leaf in self.leaves])
        self.root = self.levels[-1][0]

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> "AttributeMerkleTree":
        """
        从 DID 文档构建默克尔树

        先将文档扁平化，然后为每个属性生成叶子节点，最后构造树。

        Args:
            document: 待处理的 DID 文档字典

        Returns:
            AttributeMerkleTree: 构建完成的属性级默克尔树实例
        """
        flattened = flatten_document(document)
        leaves = []
        for path, value in flattened:
            encoded = to_canonical_json({"path": path, "value": value})
            leaves.append(
                MerkleLeaf(
                    path=path,
                    value=value,
                    encoded=encoded,
                    leaf_hash=keccak_text(encoded),
                )
            )
        return cls(leaves)

    @staticmethod
    def _build_levels(leaf_hashes: list[str]) -> list[list[str]]:
        """
        由叶子哈希逐层构建默克尔树的各级节点

        每一层通过组合相邻两个哈希（不足时复制自身）得到父节点，
        直到只剩一个根哈希。

        Args:
            leaf_hashes: 叶子层的哈希列表

        Returns:
            list[list[str]]: 从叶子到根的各层哈希列表，最后一层仅含根哈希
        """
        levels = [leaf_hashes]
        current = leaf_hashes

        while len(current) > 1:
            next_level = []
            for idx in range(0, len(current), 2):
                left = current[idx]
                right = current[idx + 1] if idx + 1 < len(current) else current[idx]
                next_level.append(combine_hashes(left, right))
            current = next_level
            levels.append(current)

        return levels

    def build_proof(self, attribute_path: str) -> dict[str, Any]:
        """
        为指定属性路径生成默克尔包含证明

        若路径不存在，抛出 KeyError。证明包含该属性的叶子哈希、
        根哈希以及从叶子到根路径上各兄弟节点的哈希和位置。

        Args:
            attribute_path: 需要证明的属性路径

        Returns:
            dict: 包含 attribute_path、attribute_value、leaf_hash、
                  merkle_root 和 proof 列表的字典

        Raises:
            KeyError: 当指定属性路径不存在于树中时抛出
        """
        if attribute_path not in self._path_to_index:
            raise KeyError(f"属性路径未找到：{attribute_path}")

        leaf_index = self._path_to_index[attribute_path]
        leaf = self.leaves[leaf_index]
        proof = []
        current_index = leaf_index

        for level in self.levels[:-1]:
            sibling_index = current_index + 1 if current_index % 2 == 0 else current_index - 1
            if sibling_index >= len(level):
                sibling_hash = level[current_index]
            else:
                sibling_hash = level[sibling_index]

            proof.append(
                {
                    "position": "right" if current_index % 2 == 0 else "left",
                    "hash": sibling_hash,
                }
            )
            current_index //= 2

        return {
            "attribute_path": leaf.path,
            "attribute_value": leaf.value,
            "leaf_hash": leaf.leaf_hash,
            "merkle_root": self.root,
            "proof": proof,
        }


def verify_proof(leaf_hash: str, proof: list[dict[str, str]], merkle_root: str) -> bool:
    """
    验证默克尔包含证明是否正确

    从叶子哈希出发，按照证明中的兄弟哈希和位置依次计算父哈希，
    最终与给定的根哈希进行比对（忽略大小写）。

    Args:
        leaf_hash: 待验证的叶子哈希（十六进制字符串）
        proof: 由 `build_proof` 生成的证明列表
        merkle_root: 预期的默克尔根哈希

    Returns:
        bool: 若计算得到的根与预期一致则返回 True，否则 False
    """
    current = leaf_hash
    for item in proof:
        if item["position"] == "right":
            current = combine_hashes(current, item["hash"])
        else:
            current = combine_hashes(item["hash"], current)
    return current.lower() == merkle_root.lower()