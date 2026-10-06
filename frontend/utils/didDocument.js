/**
 * DID 文档构建工具模块（微信小程序端）
 *
 * 本模块提供用于构建符合 W3C DID Core 规范的文档对象的函数。
 * 根据用户填写的表单字段自动生成包含 controller、verificationMethod、
 * authentication 及扩展 profile/attributes 的完整 DID 文档。
 */

const DEFAULT_CHAIN_ID = 1337;

/**
 * 根据用户提供的字段构建完整的 DID 文档。
 *
 * 文档结构遵循 W3C DID 标准，包含身份标识、控制器、验证方法、
 * 认证关系以及 profile/attributes 扩展属性。
 *
 * @param {Object} params
 * @param {string} params.did - DID 标识符，例如 "did:ethr:0x1234..."
 * @param {string} params.address - 控制器 Ethereum 地址（用于 blockchainAccountId）
 * @param {string} params.name - 用户姓名
 * @param {string} params.email - 用户邮箱
 * @param {string} params.organization - 所属组织
 * @param {string} [params.role='student'] - 用户角色，默认 "student"
 * @param {string} [params.status='active'] - 文档状态，默认 "active"
 * @param {number} [params.chainId=1337] - 区块链网络 ID，默认 1337（本地测试网）
 * @returns {Object} 构建完成的 DID 文档对象
 */
function buildDidDocument({
  did,
  address,
  name,
  email,
  organization,
  role = 'student',
  status = 'active',
  chainId = DEFAULT_CHAIN_ID
}) {
  const keyId = `${did}#controller-key-1`;

  return {
    id: did,
    controller: did,
    verificationMethod: [
      {
        id: keyId,
        type: 'EcdsaSecp256k1RecoveryMethod2020',
        controller: did,
        blockchainAccountId: `eip155:${chainId}:${address}`
      }
    ],
    authentication: [keyId],
    profile: {
      name,
      email,
      organization
    },
    attributes: {
      role,
      status
    }
  };
}

module.exports = {
  buildDidDocument
};