/**
 * DID 密钥管理工具模块（微信小程序端）
 *
 * 当前实现不使用 ethers / @noble/secp256k1。
 * 原因：
 * - ethers 在微信小程序环境中会触发 Buffer/process/elliptic 兼容问题。
 * - @noble/secp256k1 在小程序构建后会尝试 require('crypto')，导致黑屏。
 *
 * 当前实现使用：
 * - elliptic：secp256k1 椭圆曲线签名
 * - js-sha3：keccak256 哈希
 *
 * 签名格式兼容以太坊 personal_sign：
 * hash = keccak256("\x19Ethereum Signed Message:\n" + len(message) + message)
 * signature = r + s + v
 */

const elliptic = require('elliptic');
const { keccak_256 } = require('js-sha3');

const EC = elliptic.ec;
const ec = new EC('secp256k1');

/**
 * 字节数组转 hex，不带 0x。
 */
function bytesToHex(bytes) {
  return Array.prototype.map.call(bytes, (byte) => {
    return byte.toString(16).padStart(2, '0');
  }).join('');
}

/**
 * hex 转 Uint8Array。
 */
function hexToBytes(hex) {
  let value = String(hex || '').trim();

  if (value.startsWith('0x')) {
    value = value.slice(2);
  }

  if (value.length % 2 !== 0) {
    value = '0' + value;
  }

  const bytes = new Uint8Array(value.length / 2);

  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(value.slice(i * 2, i * 2 + 2), 16);
  }

  return bytes;
}

/**
 * 字符串转 UTF-8 bytes。
 */
function utf8ToBytes(str) {
  const text = String(str || '');

  if (typeof TextEncoder !== 'undefined') {
    return new TextEncoder().encode(text);
  }

  const encoded = unescape(encodeURIComponent(text));
  const bytes = new Uint8Array(encoded.length);

  for (let i = 0; i < encoded.length; i++) {
    bytes[i] = encoded.charCodeAt(i);
  }

  return bytes;
}

/**
 * 拼接多个 Uint8Array。
 */
function concatBytes() {
  const arrays = Array.prototype.slice.call(arguments);
  const totalLength = arrays.reduce((sum, arr) => sum + arr.length, 0);
  const result = new Uint8Array(totalLength);

  let offset = 0;

  arrays.forEach((arr) => {
    result.set(arr, offset);
    offset += arr.length;
  });

  return result;
}

/**
 * keccak256，返回 hex，不带 0x。
 */
function keccak256Hex(bytes) {
  return keccak_256.arrayBuffer(bytes);
}

/**
 * keccak256，返回 Uint8Array。
 */
function keccak256Bytes(bytes) {
  return new Uint8Array(keccak256Hex(bytes));
}

/**
 * 判断私钥是否在 secp256k1 有效范围内。
 *
 * 私钥必须满足：
 * 1 <= privateKey < curve.n
 */
function isValidSecp256k1PrivateKey(hex) {
  try {
    const cleanHex = String(hex || '').replace(/^0x/, '');

    if (!/^[0-9a-fA-F]{64}$/.test(cleanHex)) {
      return false;
    }

    const bn = ec.keyFromPrivate(cleanHex, 'hex').getPrivate();

    return bn.cmpn(0) > 0 && bn.cmp(ec.curve.n) < 0;
  } catch (e) {
    return false;
  }
}

/**
 * 生成随机字节。
 *
 * 注意：
 * 微信小程序的 wx.getRandomValues 不是浏览器标准 API。
 * 不要直接 wx.getRandomValues(Uint8Array)，否则容易在模拟器里异常暂停或崩溃。
 *
 */
async function randomBytes(length) {
  const res = await wx.getRandomValues({
    length
  });

  const buffer = res.randomValues;

  if (!buffer || typeof buffer.byteLength !== 'number') {
    throw new Error('wx.getRandomValues 返回值异常');
  }

  console.log('[crypto] 使用随机源: wx.getRandomValues');

  return new Uint8Array(buffer);
}
/**
 * 生成 32 字节 secp256k1 私钥。
 *
 * 增加最大尝试次数，避免任何异常情况下出现无限循环。
 */
async function createPrivateKey() {
  const maxAttempts = 32;

  for (let i = 0; i < maxAttempts; i++) {
    const bytes = await randomBytes(32);
    const hex = bytesToHex(bytes);
    const privateKey = '0x' + hex;

    if (isValidSecp256k1PrivateKey(privateKey)) {
      return privateKey;
    }
  }

  throw new Error('生成有效 secp256k1 私钥失败');
}

/**
 * 规范化私钥。
 */
function normalizePrivateKey(privateKey) {
  const value = String(privateKey || '').trim();

  if (!value) {
    throw new Error('缺少私钥');
  }

  const hex = value.startsWith('0x') ? value.slice(2) : value;

  if (!/^[0-9a-fA-F]{64}$/.test(hex)) {
    throw new Error('私钥格式错误，应为 32 字节十六进制字符串');
  }

  return '0x' + hex.toLowerCase();
}

/**
 * 私钥转 keyPair。
 */
function getKeyPairFromPrivateKey(privateKey) {
  const normalizedPrivateKey = normalizePrivateKey(privateKey);
  return ec.keyFromPrivate(normalizedPrivateKey.slice(2), 'hex');
}

/**
 * EIP-55 checksum address。
 */
function toChecksumAddress(address) {
  const raw = String(address || '').toLowerCase().replace(/^0x/, '');

  if (!/^[0-9a-f]{40}$/.test(raw)) {
    throw new Error('以太坊地址格式错误');
  }

  const hash = keccak_256(raw);
  let result = '0x';

  for (let i = 0; i < raw.length; i++) {
    result += parseInt(hash[i], 16) >= 8 ? raw[i].toUpperCase() : raw[i];
  }

  return result;
}

/**
 * 根据私钥计算以太坊地址。
 *
 * address = last20bytes(keccak256(uncompressedPublicKey[1:]))
 */
function getAddressFromPrivateKey(privateKey) {
  const keyPair = getKeyPairFromPrivateKey(privateKey);
  const publicKeyArray = keyPair.getPublic(false, 'array'); // 65 bytes, 04 + x + y
  const publicKeyWithoutPrefix = new Uint8Array(publicKeyArray.slice(1));
  const hash = keccak256Bytes(publicKeyWithoutPrefix);
  const addressBytes = hash.slice(hash.length - 20);

  return toChecksumAddress('0x' + bytesToHex(addressBytes));
}

/**
 * 生成新的 DID 控制密钥对。
 */
async function createDidKeyPair() {
  const privateKey = await createPrivateKey();
  const address = getAddressFromPrivateKey(privateKey);

  return {
    privateKey,
    address,
    did: `did:ethr:${address}`
  };
}

/**
 * 从 did:ethr:<address> 中提取地址。
 */
function extractAddressFromDid(did) {
  const prefix = 'did:ethr:';

  if (!did || !did.startsWith(prefix)) {
    throw new Error('DID格式必须为 did:ethr:<address>');
  }

  const address = did.slice(prefix.length);

  if (!address || !address.startsWith('0x')) {
    throw new Error('DID中缺少有效的以太坊地址');
  }

  return address;
}

/**
 * 地址归一化比较。
 */
function normalizeAddress(address) {
  return String(address || '').toLowerCase();
}

/**
 * 校验私钥是否属于指定 DID。
 */
function validatePrivateKeyForDid(did, privateKey) {
  const didAddress = extractAddressFromDid(did);
  const privateKeyAddress = getAddressFromPrivateKey(privateKey);

  return normalizeAddress(didAddress) === normalizeAddress(privateKeyAddress);
}

/**
 * 计算 Ethereum personal_sign 消息哈希。
 */
function getEthereumMessageHash(message) {
  const messageBytes = utf8ToBytes(message);
  const prefixBytes = utf8ToBytes(`\x19Ethereum Signed Message:\n${messageBytes.length}`);

  return keccak256Bytes(concatBytes(prefixBytes, messageBytes));
}

/**
 * 左侧补零到指定 hex 长度。
 */
function padHex(hex, length) {
  return String(hex || '').padStart(length, '0');
}

/**
 * 使用私钥签名 challenge。
 *
 * 返回 r + s + v 格式的 65 字节签名，兼容后端 eth_account.recover_message。
 */
async function signChallenge(privateKey, challenge) {
  if (!challenge) {
    throw new Error('缺少挑战消息，无法签名');
  }

  const keyPair = getKeyPairFromPrivateKey(privateKey);
  const messageHash = getEthereumMessageHash(challenge);
  const messageHashHex = bytesToHex(messageHash);

  const signature = keyPair.sign(messageHashHex, {
    canonical: true
  });

  const r = padHex(signature.r.toString('hex'), 64);
  const s = padHex(signature.s.toString('hex'), 64);
  const recoveryParam = signature.recoveryParam;

  if (recoveryParam === null || recoveryParam === undefined) {
    throw new Error('签名失败：缺少 recovery 参数');
  }

  const v = (recoveryParam + 27).toString(16).padStart(2, '0');

  return `0x${r}${s}${v}`;
}

/**
 * 根据 DID 生成对应的私钥存储键。
 */
function getPrivateKeyStorageKey(did) {
  return `didPrivateKey:${did}`;
}

/**
 * 保存 DID 私钥。
 */
function saveDidPrivateKey(did, privateKey) {
  if (!did) {
    throw new Error('缺少DID，无法保存私钥');
  }

  if (!privateKey) {
    throw new Error('缺少私钥，无法保存');
  }

  wx.setStorageSync(getPrivateKeyStorageKey(did), normalizePrivateKey(privateKey));
}

/**
 * 读取 DID 对应的本地私钥。
 */
function getDidPrivateKey(did) {
  if (!did) return '';
  return wx.getStorageSync(getPrivateKeyStorageKey(did)) || '';
}

/**
 * 判断本地是否保存了指定 DID 的私钥。
 */
function hasDidPrivateKey(did) {
  return !!getDidPrivateKey(did);
}

/**
 * 删除指定 DID 的本地私钥。
 */
function removeDidPrivateKey(did) {
  if (!did) return;
  wx.removeStorageSync(getPrivateKeyStorageKey(did));
}

module.exports = {
  createDidKeyPair,
  getAddressFromPrivateKey,
  extractAddressFromDid,
  validatePrivateKeyForDid,
  signChallenge,
  saveDidPrivateKey,
  getDidPrivateKey,
  hasDidPrivateKey,
  removeDidPrivateKey
};