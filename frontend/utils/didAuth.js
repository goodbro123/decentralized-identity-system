/**
 * DID 认证挑战与签名模块（微信小程序端）
 *
 * 本模块封装了与后端身份认证挑战的交互流程：
 * 1. 调用 /api/did/auth/challenge 获取一次性挑战原文、nonce 和时间戳
 * 2. 使用本地私钥对挑战原文签名，组装认证信息
 *
 * 使用前需确保已通过 didKeyManager 模块持有 DID 对应的私钥。
 */

const { baseURL } = require('./config');
const { signChallenge } = require('./crypto');

/**
 * 向服务端请求一次性的身份认证挑战。
 *
 * @param {Object} params - 请求参数对象。
 * @param {string} params.did - 需要进行认证的 DID 标识符。
 * @param {string} params.operation - 后续将要执行的操作类型，如 "register"、"update"。
 * @returns {Promise<Object>} 返回包含 challenge、nonce、timestamp、expires_in 等字段的对象。
 * @throws {Error} 当网络请求失败或后端返回错误时抛出，错误消息为中文描述。
 */
function requestChallenge({ did, operation }) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: baseURL + '/api/did/auth/challenge',
      method: 'POST',
      header: {
        'content-type': 'application/json'
      },
      data: {
        did,
        operation
      },
      success: (res) => {
        const payload = res.data || {};

        if (res.statusCode < 200 || res.statusCode >= 300 || payload.success === false) {
          reject(new Error(payload.message || '获取挑战失败'));
          return;
        }

        resolve(payload.data || payload);
      },
      fail: () => {
        reject(new Error('网络请求失败'));
      }
    });
  });
}

/**
 * 一键获取挑战并利用本地私钥完成签名，组装为认证信息对象。
 *
 * 该函数组合了 requestChallenge 和 signChallenge 两个步骤，
 * 返回的 auth 对象可直接放入后续业务请求的 auth 字段中。
 *
 * @param {Object} params - 参数对象。
 * @param {string} params.did - DID 标识符。
 * @param {string} params.operation - 操作类型，同 requestChallenge。
 * @param {string} params.privateKey - DID 控制者的私钥（十六进制字符串）。
 * @returns {Promise<Object>} 包含 operation、nonce、timestamp 和 signature 的认证信息。
 */
async function buildDidAuthWithPrivateKey({ did, operation, privateKey }) {
  const challengeData = await requestChallenge({
    did,
    operation
  });

  const signature = await signChallenge(privateKey, challengeData.challenge);

  return {
    operation,
    nonce: challengeData.nonce,
    timestamp: challengeData.timestamp,
    signature
  };
}

module.exports = {
  requestChallenge,
  buildDidAuthWithPrivateKey
}; 