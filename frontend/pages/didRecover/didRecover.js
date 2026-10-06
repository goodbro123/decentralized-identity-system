const { baseURL } = require('../../utils/config');
const {
  checkDidReachable,
  checkDidController
} = require('../../utils/auth');
const { formatBeijingTime } = require('../../utils/format');

function getDidAuthUtils() {
  return require('../../utils/didAuth');
}

function getCryptoUtils() {
  return require('../../utils/crypto');
}

function normalizeBoolean(value) {
  if (value === true) return true;
  if (value === false) return false;
  if (value === 'true') return true;
  if (value === 'false') return false;
  if (value === 1) return true;
  if (value === 0) return false;
  return null;
}

function parseMissingIndexes(value) {
  const text = String(value || '').trim();

  if (!text) {
    return [];
  }

  const parts = text
    .split(',')
    .map(item => item.trim())
    .filter(Boolean);

  const indexes = [];

  for (let i = 0; i < parts.length; i++) {
    const num = Number(parts[i]);

    if (!Number.isInteger(num) || num < 0) {
      return null;
    }

    indexes.push(num);
  }

  return indexes;
}

Page({
  data: {
    did: '',
    currentDid: '',
    hasPrivateKey: false,
    documentMissing: false,
    version: '',

    recoverMethod: 'auto',
    missingIndexesText: '',

    backendOk: false,
    loading: false,
    recovering: false,
    recovered: false,

    recoverResult: null,
    recoverResultJson: '',

    latestResult: null,
    chainState: null,
    currentDocument: null,

    verifyResult: null,
    verifyResultJson: '',

    isValid: null,
    recoverTimeText: '-',

    summaryText: '未恢复',
    summaryDesc: '请输入 DID 后发起链下数据恢复。',
    summaryClass: 'idle',

    checkItems: [],

    methodOptions: [
      {
        key: 'auto',
        title: '自动恢复',
        desc: '由后端自动选择可用恢复策略'
      },
      {
        key: 'duplication',
        title: '多副本恢复',
        desc: '从副本数据中恢复 DID 文档'
      },
      {
        key: 'erasure_code',
        title: '纠删码恢复',
        desc: '从纠删码数据块中重建 DID 文档'
      }
    ]
  },

  onLoad(options) {
    const currentDid = wx.getStorageSync('currentDid') || '';
    const routeDid = options.did ? decodeURIComponent(options.did) : '';

    this.setData({
      did: routeDid || currentDid,
      currentDid,
      version: options.version || ''
    });
  },

  onShow() {
    checkDidReachable({
      did: this.data.did,
      success: ({ currentDid, hasPrivateKey, documentMissing }) => {
        this.setData({
          currentDid,
          did: this.data.did || currentDid,
          hasPrivateKey,
          documentMissing
        });
      }
    });

    this.checkBackend();
  },

  checkBackend() {
    wx.request({
      url: baseURL + '/health',
      method: 'GET',
      success: (res) => {
        this.setData({
          backendOk: res.statusCode >= 200 && res.statusCode < 300
        });
      },
      fail: () => {
        this.setData({
          backendOk: false
        });
      }
    });
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;

    this.setData({
      [field]: e.detail.value
    });
  },

  selectRecoverMethod(e) {
    const method = e.currentTarget.dataset.method;

    this.setData({
      recoverMethod: method
    });
  },

  validateDid() {
    const did = (this.data.did || '').trim();

    if (!did) {
      wx.showToast({
        title: 'DID不能为空',
        icon: 'none'
      });
      return '';
    }

    if (!did.startsWith('did:')) {
      wx.showToast({
        title: 'DID必须以did:开头',
        icon: 'none'
      });
      return '';
    }

    return did;
  },

  useCurrentDid() {
    const currentDid = wx.getStorageSync('currentDid') || '';

    if (!currentDid) {
      wx.showToast({
        title: '当前未绑定DID',
        icon: 'none'
      });
      return;
    }

    this.setData({
      did: currentDid,
      version: ''
    });
  },

  buildRequestBody(did) {
    const body = {
      did
    };

    const version = (this.data.version || '').trim();

    if (version) {
      const versionNumber = Number(version);

      if (!Number.isInteger(versionNumber) || versionNumber <= 0) {
        wx.showToast({
          title: '版本号必须为正整数',
          icon: 'none'
        });
        return null;
      }

      body.version = versionNumber;
    }

    if (this.data.recoverMethod && this.data.recoverMethod !== 'auto') {
      body.force_method = this.data.recoverMethod;
    }

    const missingIndexes = parseMissingIndexes(this.data.missingIndexesText);

    if (missingIndexes === null) {
      wx.showToast({
        title: '丢失索引格式错误',
        icon: 'none'
      });
      return null;
    }

    body.missing_data_indexes = missingIndexes;

    return body;
  },

  startRecover() {
    const did = this.validateDid();
    if (!did) return;

    const requestBody = this.buildRequestBody(did);
    if (!requestBody) return;

    checkDidController({
      did,
      success: () => {
        wx.showModal({
          title: '确认数据恢复',
          content: '恢复操作会重建链下 DID 文档，并在恢复后自动查询状态和执行身份认证。是否继续？',
          confirmText: '恢复',
          confirmColor: '#4C8DFF',
          cancelText: '取消',
          success: (modalRes) => {
            if (!modalRes.confirm) return;

            this.doRecover(requestBody);
          }
        });
      }
    });
  },

  async doRecover(requestBody) {
    this.setData({
      loading: true,
      recovering: true,
      recovered: false,

      recoverResult: null,
      recoverResultJson: '',
      latestResult: null,
      chainState: null,
      currentDocument: null,
      verifyResult: null,
      verifyResultJson: '',
      checkItems: []
    });

    try {
      const { buildDidAuthWithPrivateKey } = getDidAuthUtils();
      const { getDidPrivateKey } = getCryptoUtils();

      const privateKey = getDidPrivateKey(requestBody.did);

      if (!privateKey) {
        throw new Error('当前设备没有该 DID 私钥');
      }

      const auth = await buildDidAuthWithPrivateKey({
        did: requestBody.did,
        operation: 'recover',
        privateKey
      });

      wx.request({
        url: baseURL + '/api/did/recover',
        method: 'POST',
        data: {
          ...requestBody,
          auth
        },
        header: {
          'content-type': 'application/json'
        },
        success: (res) => {
          const payload = res.data || {};

          if (res.statusCode < 200 || res.statusCode >= 300 || payload.success === false) {
            wx.showToast({
              title: payload.message || '恢复失败',
              icon: 'none'
            });

            this.setFailedResult(payload);
            return;
          }

          const data = payload.data || payload;

          this.handleRecoverResult(data);

          wx.showToast({
            title: '恢复完成',
            icon: 'success'
          });

          this.afterRecoverCheck(requestBody.did);
        },
        fail: () => {
          wx.showToast({
            title: '网络请求失败',
            icon: 'none'
          });

          this.setFailedResult({
            message: '网络请求失败'
          });
        },
        complete: () => {
          this.setData({
            loading: false,
            recovering: false
          });

          this.checkBackend();
        }
      });
    } catch (e) {
      wx.showToast({
        title: e.message || '恢复签名失败',
        icon: 'none'
      });

      this.setFailedResult({
        message: e.message || '恢复签名失败'
      });

      this.setData({
        loading: false,
        recovering: false
      });
    }
  },

  handleRecoverResult(data) {
    let recoverResultJson = '';

    try {
      recoverResultJson = JSON.stringify(data, null, 2);
    } catch (e) {
      recoverResultJson = String(data);
    }

    const isValid = normalizeBoolean(data.is_valid);
    const checkItems = this.buildRecoverCheckItems(data);

    this.setData({
      recoverResult: data,
      recoverResultJson,

      recovered: true,
      isValid,
      recoverTimeText: formatBeijingTime(Date.now()),
      checkItems,

      summaryText: isValid ? '恢复可信' : '恢复未通过校验',
      summaryDesc: isValid
        ? '链下 DID 文档已恢复，并通过本地摘要与链上状态校验。系统将继续自动查询状态和执行认证。'
        : '恢复操作已返回结果，但至少一项完整性校验未通过。',
      summaryClass: isValid ? 'success' : 'danger'
    });
  },

  setFailedResult(payload) {
    let recoverResultJson = '';

    try {
      recoverResultJson = JSON.stringify(payload, null, 2);
    } catch (e) {
      recoverResultJson = String(payload);
    }

    this.setData({
      recoverResult: payload,
      recoverResultJson,

      recovered: true,
      isValid: false,
      recoverTimeText: formatBeijingTime(Date.now()),

      summaryText: '恢复请求失败',
      summaryDesc: payload.message || payload.error || '后端未返回有效恢复结果。',
      summaryClass: 'danger',

      checkItems: []
    });
  },

  afterRecoverCheck(did) {
    this.queryLatestAfterRecover(did);
    this.verifyAfterRecover(did);
  },

  queryLatestAfterRecover(did) {
    wx.request({
      url: baseURL + '/api/did/latest',
      method: 'GET',
      data: {
        did
      },
      header: {
        'content-type': 'application/json'
      },
      success: (res) => {
        const payload = res.data || {};

        if (res.statusCode < 200 || res.statusCode >= 300 || payload.success === false) {
          return;
        }

        const data = payload.data || payload;
        const chainState = data.chain_state || data.chainState || {};
        const currentDocument = data.current_document || data.currentDocument || null;

        this.setData({
          latestResult: data,
          chainState,
          currentDocument,
          documentMissing: !currentDocument
        });
      }
    });
  },

  verifyAfterRecover(did) {
    wx.request({
      url: baseURL + '/api/did/verify',
      method: 'POST',
      data: {
        did
      },
      header: {
        'content-type': 'application/json'
      },
      success: (res) => {
        const payload = res.data || {};

        if (res.statusCode < 200 || res.statusCode >= 300 || payload.success === false) {
          return;
        }

        const data = payload.data || payload;

        let verifyResultJson = '';

        try {
          verifyResultJson = JSON.stringify(data, null, 2);
        } catch (e) {
          verifyResultJson = String(data);
        }

        this.setData({
          verifyResult: data,
          verifyResultJson
        });
      }
    });
  },

  buildRecoverCheckItems(data) {
    const localIntegrity = normalizeBoolean(data.local_integrity_ok);
    const chainIntegrity = normalizeBoolean(data.chain_integrity_ok);
    const isValid = normalizeBoolean(data.is_valid);

    const itemDefs = [
      {
        key: 'local_integrity_ok',
        title: '本地恢复完整性',
        desc: '恢复后的 DID 文档重新计算摘要，并与恢复块保存的摘要比对。',
        value: localIntegrity
      },
      {
        key: 'chain_integrity_ok',
        title: '链上状态一致性',
        desc: '当恢复版本为链上最新版本时，检查恢复结果是否与链上状态一致。',
        value: chainIntegrity
      },
      {
        key: 'is_valid',
        title: '最终恢复可信性',
        desc: '本地完整性和链上一致性均通过，恢复结果才可信。',
        value: isValid
      }
    ];

    return itemDefs.map(item => {
      const value = item.value;

      return {
        key: item.key,
        title: item.title,
        desc: item.desc,
        status: value,
        statusText: value === true ? '通过' : value === false ? '失败' : '未检测',
        statusClass: value === true ? 'success' : value === false ? 'danger' : 'warning'
      };
    });
  },

  copyRecoverJson() {
    if (!this.data.recoverResultJson) {
      wx.showToast({
        title: '暂无恢复结果',
        icon: 'none'
      });
      return;
    }

    wx.setClipboardData({
      data: this.data.recoverResultJson,
      success: () => {
        wx.showToast({
          title: '恢复结果已复制',
          icon: 'success'
        });
      }
    });
  },

  copyVerifyJson() {
    if (!this.data.verifyResultJson) {
      wx.showToast({
        title: '暂无认证结果',
        icon: 'none'
      });
      return;
    }

    wx.setClipboardData({
      data: this.data.verifyResultJson,
      success: () => {
        wx.showToast({
          title: '认证结果已复制',
          icon: 'success'
        });
      }
    });
  },

  copyHash(e) {
    const value = e.currentTarget.dataset.value || '';

    if (!value) {
      wx.showToast({
        title: '暂无内容可复制',
        icon: 'none'
      });
      return;
    }

    wx.setClipboardData({
      data: String(value),
      success: () => {
        wx.showToast({
          title: '已复制',
          icon: 'success'
        });
      }
    });
  },

  goLatest() {
    wx.navigateTo({
      url: `/pages/didLatest/didLatest?did=${encodeURIComponent(this.data.did)}`
    });
  },

  goVerify() {
    wx.navigateTo({
      url: `/pages/didVerify/didVerify?did=${encodeURIComponent(this.data.did)}`
    });
  },

  goOperation() {
    wx.switchTab({
      url: '/pages/release/release'
    });
  }
});