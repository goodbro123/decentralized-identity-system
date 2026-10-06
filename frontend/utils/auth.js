const { baseURL } = require('./config');

const LOGIN_URL = '/pages/login/login';

let isRedirectingToLogin = false;

function getCurrentRoute() {
  const pages = getCurrentPages();
  const currentPage = pages[pages.length - 1];

  if (!currentPage || !currentPage.route) {
    return '';
  }

  return '/' + currentPage.route;
}

function redirectToLogin(message) {
  const currentRoute = getCurrentRoute();

  if (currentRoute === LOGIN_URL) {
    return;
  }

  if (isRedirectingToLogin) {
    return;
  }

  isRedirectingToLogin = true;

  if (message) {
    wx.showToast({
      title: message,
      icon: 'none',
      duration: 1000
    });
  }

  setTimeout(() => {
    wx.reLaunch({
      url: LOGIN_URL,
      complete: () => {
        isRedirectingToLogin = false;
      }
    });
  }, message ? 700 : 0);
}

function getPrivateKeyStorageKey(did) {
  return `didPrivateKey:${did}`;
}

function hasDidPrivateKeyLocal(did) {
  if (!did) return false;
  return !!wx.getStorageSync(getPrivateKeyStorageKey(did));
}

/**
 * 只清除当前绑定状态。
 *
 * 注意：
 * 默认不删除 didPrivateKey:<did>。
 * 因为“解除当前绑定”和“删除本地控制私钥”不是同一件事。
 */
function clearDidSession() {
  wx.removeStorageSync('currentDid');
  wx.removeStorageSync('currentDidInfo');
}

/**
 * 清除当前绑定，并删除当前 DID 的本地私钥。
 *
 * 只有用户明确选择“删除身份私钥”时才调用。
 */
function clearDidSessionWithPrivateKey() {
  const currentDid = wx.getStorageSync('currentDid') || '';

  clearDidSession();

  if (currentDid) {
    wx.removeStorageSync(getPrivateKeyStorageKey(currentDid));
  }
}

/**
 * 本地 DID 状态检查。
 *
 * 只检查：
 * 1. 本地是否有 currentDid
 * 2. 本地是否有 didPrivateKey:<did>
 *
 * 不请求后端。
 *
 * 适用：
 * - 我的页
 * - 页面初始化展示本地状态
 * - 判断是否拥有本机控制私钥
 */
function checkDidLocal(options = {}) {
  const {
    redirect = true,
    success,
    fail
  } = options;

  const currentDid = wx.getStorageSync('currentDid') || '';

  if (!currentDid) {
    if (redirect) {
      redirectToLogin('请先创建或导入 DID');
    }

    if (typeof fail === 'function') {
      fail({
        reason: 'NO_CURRENT_DID'
      });
    }

    return;
  }

  const hasPrivateKey = hasDidPrivateKeyLocal(currentDid);

  if (typeof success === 'function') {
    success({
      currentDid,
      hasPrivateKey
    });
  }
}

/**
 * 检查 DID 是否链上可达。
 *
 * 允许链下 current_document 缺失。
 *
 * 适用：
 * - 首页 index
 * - 操作页 release
 * - 我的页 my
 * - 状态查询 didLatest
 * - 数据恢复 didRecover
 *
 * 重要：
 * 链下文档缺失时，不能清除 currentDid。
 * 因为这正是数据恢复页面要处理的异常状态。
 */
function checkDidReachable(options = {}) {
  const {
    did,
    redirect = true,
    success,
    fail
  } = options;

  const targetDid = did || wx.getStorageSync('currentDid') || '';

  if (!targetDid) {
    if (redirect) {
      redirectToLogin('请先创建或导入 DID');
    }

    if (typeof fail === 'function') {
      fail({
        reason: 'NO_CURRENT_DID'
      });
    }

    return;
  }

  wx.request({
    url: baseURL + '/api/did/latest',
    method: 'GET',
    data: {
      did: targetDid
    },
    header: {
      'content-type': 'application/json'
    },
    success: (res) => {
      const payload = res.data || {};

      if (res.statusCode < 200 || res.statusCode >= 300 || payload.success === false) {
        if (redirect) {
          redirectToLogin(payload.message || 'DID 状态异常');
        }

        if (typeof fail === 'function') {
          fail({
            reason: 'REQUEST_FAILED',
            response: payload
          });
        }

        return;
      }

      const data = payload.data || payload;
      const chainState = data.chain_state || data.chainState || {};
      const currentDocument = data.current_document || data.currentDocument || null;

      /**
       * 后端如果明确返回 exists: false，说明链上不存在。
       * 如果后端暂时没有 exists 字段，只要 latest 接口成功，就认为链上可达。
       */
      const chainExists = chainState.exists !== false;

      if (!chainExists) {
        if (redirect) {
          redirectToLogin('DID 未在链上注册');
        }

        if (typeof fail === 'function') {
          fail({
            reason: 'DID_NOT_ON_CHAIN',
            response: data
          });
        }

        return;
      }

      const hasPrivateKey = hasDidPrivateKeyLocal(targetDid);
      const documentMissing = !currentDocument;

      wx.setStorageSync('currentDid', targetDid);
      wx.setStorageSync('currentDidInfo', data);

      if (typeof success === 'function') {
        success({
          currentDid: targetDid,
          hasPrivateKey,
          didInfo: data,
          chainState,
          currentDocument,
          documentMissing
        });
      }
    },
    fail: (err) => {
      if (redirect) {
        wx.showToast({
          title: '网络请求失败',
          icon: 'none'
        });
      }

      if (typeof fail === 'function') {
        fail({
          reason: 'NETWORK_ERROR',
          error: err
        });
      }
    }
  });
}

/**
 * 严格 DID 可用状态检查。
 *
 * 要求：
 * 1. 本地有 currentDid
 * 2. 链上 DID 存在
 * 3. 链下 current_document 存在
 *
 * 适用：
 * - DID 更新 didUpdate
 * - 身份认证 didVerify
 * - 属性证明 didProof
 *
 * 注意：
 * 如果链下文档缺失，不跳登录、不清 currentDid，而是提示去恢复。
 */
function checkDidReady(options = {}) {
  const {
    redirect = true,
    success,
    fail
  } = options;

  checkDidReachable({
    redirect,
    success: ({ currentDid, hasPrivateKey, didInfo, chainState, currentDocument, documentMissing }) => {
      if (documentMissing) {
        if (redirect) {
          wx.showModal({
            title: '链下文档缺失',
            content: '当前 DID 已在链上注册，但链下 DID 文档缺失。请先进行数据恢复。',
            confirmText: '去恢复',
            cancelText: '取消',
            success: (modalRes) => {
              if (modalRes.confirm) {
                wx.navigateTo({
                  url: `/pages/didRecover/didRecover?did=${encodeURIComponent(currentDid)}`
                });
              }
            }
          });
        }

        if (typeof fail === 'function') {
          fail({
            reason: 'CURRENT_DOCUMENT_MISSING',
            currentDid,
            hasPrivateKey,
            didInfo,
            chainState
          });
        }

        return;
      }

      if (typeof success === 'function') {
        success({
          currentDid,
          hasPrivateKey,
          didInfo,
          chainState,
          currentDocument
        });
      }
    },
    fail
  });
}

/**
 * DID 控制私钥检查。
 *
 * 只检查本地是否保存 didPrivateKey:<did>。
 * 真正的控制权认证仍然要通过：
 * challenge -> 本地签名 -> 后端验签。
 *
 * 适用：
 * - 点击 DID 更新前
 * - 点击数据恢复前
 */
function checkDidController(options = {}) {
  const {
    did,
    showToast = true,
    success,
    fail
  } = options;

  const targetDid = did || wx.getStorageSync('currentDid') || '';

  if (!targetDid) {
    if (showToast) {
      wx.showToast({
        title: '请先创建或导入 DID',
        icon: 'none'
      });
    }

    if (typeof fail === 'function') {
      fail({
        reason: 'NO_CURRENT_DID'
      });
    }

    return;
  }

  if (!hasDidPrivateKeyLocal(targetDid)) {
    if (showToast) {
      wx.showToast({
        title: '当前设备没有该 DID 私钥',
        icon: 'none'
      });
    }

    if (typeof fail === 'function') {
      fail({
        reason: 'NO_DID_PRIVATE_KEY',
        currentDid: targetDid
      });
    }

    return;
  }

  if (typeof success === 'function') {
    success({
      currentDid: targetDid
    });
  }
}

/**
 * 兼容旧页面。
 *
 * 以前页面里如果还在调用 checkDidSession，
 * 暂时让它等价于 checkDidReady。
 *
 * 后续建议逐步把页面里的 checkDidSession 改成：
 * - checkDidReachable
 * - checkDidReady
 * - checkDidController
 */
function checkDidSession(options = {}) {
  checkDidReady(options);
}

function getCurrentDid() {
  return wx.getStorageSync('currentDid') || '';
}

function setCurrentDid(did, didInfo) {
  wx.setStorageSync('currentDid', did);

  if (didInfo) {
    wx.setStorageSync('currentDidInfo', didInfo);
  }
}

function getCurrentDidInfo() {
  return wx.getStorageSync('currentDidInfo') || null;
}

function verifyDidIntegrityOrRecover(options = {}) {
  const {
    did,
    version,
    actionName = '当前操作',
    success,
    fail
  } = options;

  const targetDid = did || wx.getStorageSync('currentDid') || '';

  if (!targetDid) {
    wx.showToast({
      title: '请先创建或导入 DID',
      icon: 'none'
    });

    if (typeof fail === 'function') {
      fail({
        reason: 'NO_CURRENT_DID'
      });
    }
    return;
  }

  const body = {
    did: targetDid
  };

  if (version) {
    body.version = Number(version);
  }

  wx.showLoading({
    title: '正在验证 DID'
  });

  wx.request({
    url: baseURL + '/api/did/verify',
    method: 'POST',
    data: body,
    header: {
      'content-type': 'application/json'
    },
    success: (res) => {
      const payload = res.data || {};

      /**
       * 注意：
       * verify 接口 HTTP 200 只代表接口正常返回，
       * 不代表 DID 文档一定可信。
       * 真正的验证结果要看 data.is_valid。
       */
      if (res.statusCode < 200 || res.statusCode >= 300 || payload.success === false) {
        wx.showModal({
          title: '验证失败',
          content: payload.message || '当前 DID 状态异常，请先尝试数据恢复。',
          confirmText: '去恢复',
          cancelText: '取消',
          success: (modalRes) => {
            if (modalRes.confirm) {
              wx.navigateTo({
                url: `/pages/didRecover/didRecover?did=${encodeURIComponent(targetDid)}`
              });
            }
          }
        });

        if (typeof fail === 'function') {
          fail({
            reason: 'VERIFY_REQUEST_FAILED',
            response: payload
          });
        }
        return;
      }

      const data = payload.data || {};
      const isValid = data.is_valid === true || data.isValid === true;

      if (!isValid) {
        wx.showModal({
          title: 'DID 验证未通过',
          content: `${actionName}前检测到链上链下数据不一致，建议先进行数据恢复。`,
          confirmText: '去恢复',
          cancelText: '取消',
          success: (modalRes) => {
            if (modalRes.confirm) {
              wx.navigateTo({
                url: `/pages/didRecover/didRecover?did=${encodeURIComponent(targetDid)}`
              });
            }
          }
        });

        if (typeof fail === 'function') {
          fail({
            reason: 'DID_VERIFY_INVALID',
            verifyResult: data
          });
        }
        return;
      }

      if (typeof success === 'function') {
        success({
          currentDid: targetDid,
          verifyResult: data
        });
      }
    },
    fail: (err) => {
      wx.showToast({
        title: '验证请求失败',
        icon: 'none'
      });

      if (typeof fail === 'function') {
        fail({
          reason: 'NETWORK_ERROR',
          error: err
        });
      }
    },
    complete: () => {
      wx.hideLoading();
    }
  });
}

module.exports = {
  verifyDidIntegrityOrRecover,
  checkDidLocal,
  checkDidReachable,
  checkDidReady,
  checkDidController,
  checkDidSession,

  clearDidSession,
  clearDidSessionWithPrivateKey,

  getCurrentDid,
  getCurrentDidInfo,
  setCurrentDid
};