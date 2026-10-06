const { baseURL } = require('../../utils/config');
const { checkDidReady } = require('../../utils/auth');
const { formatBeijingTime } = require('../../utils/format');

function normalizeBoolean(value) {
  if (value === true) return true;
  if (value === false) return false;
  if (value === 'true') return true;
  if (value === 'false') return false;
  if (value === 1) return true;
  if (value === 0) return false;
  return null;
}

Page({
  data: {
    did: '',
    currentDid: '',
    version: '',

    backendOk: false,
    loading: false,
    verifying: false,
    verified: false,

    verifyResult: null,
    resultJson: '',

    isValid: null,
    verifyTimeText: '-',

    summaryText: '未认证',
    summaryDesc: '请输入 DID 后发起身份认证。',
    summaryClass: 'idle',

    checkItems: [],
    errorList: [],

    chainState: null,
    recomputedTarget: null,
    transactionStatus: null
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
    checkDidReady({
      success: ({ currentDid }) => {
        this.setData({
          currentDid,
          did: this.data.did || currentDid
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

    return body;
  },

  startVerify() {
    const did = this.validateDid();
    if (!did) return;

    const requestBody = this.buildRequestBody(did);
    if (!requestBody) return;

    this.setData({
      loading: true,
      verifying: true,
      verified: false
    });

    wx.request({
      url: baseURL + '/api/did/verify',
      method: 'POST',
      data: requestBody,
      header: {
        'content-type': 'application/json'
      },
      success: (res) => {
        const payload = res.data || {};

        if (res.statusCode < 200 || res.statusCode >= 300 || payload.success === false) {
          wx.showToast({
            title: payload.message || '认证失败',
            icon: 'none'
          });

          this.setFailedResult(payload);
          return;
        }

        const data = payload.data || payload;

        this.handleVerifyResult(data);

        wx.showToast({
          title: '认证完成',
          icon: 'success'
        });
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
          verifying: false
        });

        this.checkBackend();
      }
    });
  },

  handleVerifyResult(data) {
    let resultJson = '';

    try {
      resultJson = JSON.stringify(data, null, 2);
    } catch (e) {
      resultJson = String(data);
    }

    const isValid = this.extractOverallValid(data);
    const checkItems = this.buildCheckItems(data);
    const errorList = this.extractErrors(data);

    const chainState = data.chain_state || data.chainState || null;
    const recomputedTarget = data.recomputed_target || data.recomputedTarget || null;
    const transactionStatus = data.transaction_status || data.transactionStatus || null;

    this.setData({
      verifyResult: data,
      resultJson,

      verified: true,
      isValid,
      verifyTimeText: formatBeijingTime(Date.now()),

      checkItems,
      errorList,

      chainState,
      recomputedTarget,
      transactionStatus,

      summaryText: isValid ? '认证通过' : '认证未通过',
      summaryDesc: isValid
        ? '当前 DID 的链上状态、链下文档摘要、默克尔根和版本哈希链均通过校验。'
        : '当前 DID 未通过全部校验，请查看分项结果、交易状态与错误详情。',
      summaryClass: isValid ? 'success' : 'danger'
    });
  },

  setFailedResult(payload) {
    let resultJson = '';

    try {
      resultJson = JSON.stringify(payload, null, 2);
    } catch (e) {
      resultJson = String(payload);
    }

    this.setData({
      verifyResult: payload,
      resultJson,

      verified: true,
      isValid: false,
      verifyTimeText: formatBeijingTime(Date.now()),

      summaryText: '认证请求失败',
      summaryDesc: payload.message || payload.error || '后端未返回有效认证结果。',
      summaryClass: 'danger',

      checkItems: [],
      errorList: this.extractErrors(payload),

      chainState: null,
      recomputedTarget: null,
      transactionStatus: null
    });
  },

  extractOverallValid(data) {
    const value = normalizeBoolean(data.is_valid);

    if (value !== null) {
      return value;
    }

    const fallback = normalizeBoolean(data.isValid);

    if (fallback !== null) {
      return fallback;
    }

    return false;
  },

  buildCheckItems(data) {
    const itemDefs = [
      {
        key: 'target_document_hash_match',
        title: '文档哈希校验',
        desc: '重新计算目标 DID 文档哈希，并与记录中的 document_hash 比对。',
        value: data.target_document_hash_match
      },
      {
        key: 'target_merkle_root_match',
        title: '默克尔根校验',
        desc: '重新计算属性级默克尔树根，并与目标版本记录中的 merkle_root 比对。',
        value: data.target_merkle_root_match
      },
      {
        key: 'target_version_hash_match',
        title: '目标版本哈希校验',
        desc: '校验目标版本的 version_hash 是否由当前版本内容正确计算得到。',
        value: data.target_version_hash_match
      },
      {
        key: 'history_chain_valid',
        title: '版本历史连续性',
        desc: '检查 DID 历史版本哈希链是否连续，防止旧版本回滚或历史断裂。',
        value: data.history_chain_valid
      },
      {
        key: 'latest_chain_match',
        title: '链上状态匹配',
        desc: '确认链下最新版本状态与智能合约中的 DID 状态锚点一致。',
        value: data.latest_chain_match
      },
      {
        key: 'transaction_verified',
        title: '交易状态校验',
        desc: '通过链上交易状态确认相关注册或更新交易是否成功。',
        value: data.transaction_verified
      }
    ];

    return itemDefs.map(item => {
      const value = normalizeBoolean(item.value);

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

  extractErrors(data) {
    const raw =
      data.history_errors ||
      data.historyErrors ||
      data.errors ||
      data.error_list ||
      data.errorList ||
      data.message ||
      data.error ||
      [];

    if (Array.isArray(raw)) {
      return raw.map(item => String(item));
    }

    if (typeof raw === 'string') {
      return raw ? [raw] : [];
    }

    try {
      return [JSON.stringify(raw)];
    } catch (e) {
      return [];
    }
  },

  copyResultJson() {
    if (!this.data.resultJson) {
      wx.showToast({
        title: '暂无认证结果',
        icon: 'none'
      });
      return;
    }

    wx.setClipboardData({
      data: this.data.resultJson,
      success: () => {
        wx.showToast({
          title: '认证结果已复制',
          icon: 'success'
        });
      }
    });
  },

  copyText(e) {
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

  goOperation() {
    wx.switchTab({
      url: '/pages/release/release'
    });
  }
});