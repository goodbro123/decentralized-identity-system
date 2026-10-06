// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title DIDState 智能合约
 * @notice 本合约用于记录去中心化身份（DID）的链上状态锚点。
 *         存储 DID 的最新版本号、文档摘要、默克尔根及版本哈希链值，
 *         为链下不可信存储环境提供可信的校验依据。
 * @dev 每个 DID 的状态通过 bytes32 类型的 didKey 进行索引。
 */
contract DIDState {

    /**
     * @dev DID 状态结构体，保存单个 DID 的完整链上信息
     * @param exists 标识该 DID 是否已注册
     * @param version 当前最新版本号
     * @param documentHash 最新版本 DID 文档的摘要（bytes32）
     * @param merkleRoot 属性级默克尔树的根哈希（bytes32）
     * @param versionHash 版本哈希链的最新值（bytes32）
     * @param updatedAt 最后更新时间戳（Unix 秒）
     */
    struct State {
        bool exists;
        uint256 version;
        bytes32 documentHash;
        bytes32 merkleRoot;
        bytes32 versionHash;
        uint256 updatedAt;
    }

    // 以 didKey 为键，存储各 DID 的最新状态
    mapping(bytes32 => State) private latestStates;

    /**
     * @dev 当 DID 状态被更新时触发该事件
     * @param didKey 被更新的 DID 对应的键（bytes32）
     * @param version 更新后的版本号
     * @param documentHash 更新后的文档摘要
     * @param merkleRoot 更新后的默克尔根
     * @param versionHash 更新后的版本哈希链值
     * @param updatedAt 更新的时间戳
     */
    event DIDStateUpdated(
        bytes32 indexed didKey,
        uint256 version,
        bytes32 documentHash,
        bytes32 merkleRoot,
        bytes32 versionHash,
        uint256 updatedAt
    );

    /**
     * @notice 更新指定 DID 的链上状态
     * @dev 首次注册时版本号必须为 1；已存在的 DID 更新时版本号必须严格递增 1。
     * @param didKey DID 的链上标识符（bytes32）
     * @param version 新版本号
     * @param documentHash 新版本 DID 文档的摘要
     * @param merkleRoot 新版本的属性级默克尔树根
     * @param versionHash 新版本的哈希链值
     */
    function updateState(
        bytes32 didKey,
        uint256 version,
        bytes32 documentHash,
        bytes32 merkleRoot,
        bytes32 versionHash
    ) external {
        State storage current = latestStates[didKey];

        if (!current.exists) {
            require(version == 1, unicode"首次注册时版本号必须为 1");
            current.exists = true;
        } else {
            require(version == current.version + 1, unicode"版本号必须严格递增 1");
        }

        current.version = version;
        current.documentHash = documentHash;
        current.merkleRoot = merkleRoot;
        current.versionHash = versionHash;
        current.updatedAt = block.timestamp;

        emit DIDStateUpdated(
            didKey,
            version,
            documentHash,
            merkleRoot,
            versionHash,
            block.timestamp
        );
    }

    /**
     * @notice 查询指定 DID 的最新链上状态
     * @param didKey DID 的链上标识符（bytes32）
     * @return exists 该 DID 是否已注册
     * @return version 当前最新版本号
     * @return documentHash 当前文档摘要
     * @return merkleRoot 当前默克尔根
     * @return versionHash 当前版本哈希链值
     * @return updatedAt 最后更新时间戳
     */
    function getLatest(bytes32 didKey)
        external
        view
        returns (
            bool exists,
            uint256 version,
            bytes32 documentHash,
            bytes32 merkleRoot,
            bytes32 versionHash,
            uint256 updatedAt
        )
    {
        State storage current = latestStates[didKey];
        return (
            current.exists,
            current.version,
            current.documentHash,
            current.merkleRoot,
            current.versionHash,
            current.updatedAt
        );
    }
}