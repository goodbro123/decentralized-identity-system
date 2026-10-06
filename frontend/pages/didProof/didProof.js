const { baseURL } = require('../../utils/config');
const { checkDidReachable } = require('../../utils/auth');

function safeJsonStringify(value) {
  try {
    return JSON.stringify(value || {}, null, 2);
  } catch (e) {
    return '';
  }
}

function normalizeProofResult(data) {
  const proof = data.proof || data.merkle_proof || {};

  const proofList =
    proof.proof ||
    proof.path ||
    proof.siblings ||
    data.proof_path ||
    [];

  return {
    did: data.did || '',
    version: data.version || data.requested_version || '',
    attributePath: data.attribute_path || proof.attribute_path || '',
    attributeValue: proof.attribute_value,
    leafHash: proof.leaf_hash || data.leaf_hash || '',
    merkleRoot: proof.merkle_root || data.merkle_root || '',
    proofList: Array.isArray(proofList) ? proofList : [],
    rawProof: proof
  };
}

Page({
  data: {
    did: '',
    currentDid: '',
    version: '',
    attributePath: '',

    backendOk: false,
    hasPrivateKey: false,
    documentMissing: false,

    loading: false,
    queried: false,

    result: null,
    normalized: null,
    proofItems: [],
    resultJson: '',

    commonAttributes: [
      // 一、推荐证明的业务属性
      {
        label: '姓名',
        value: 'profile.name'
      },
      {
        label: '组织',
        value: 'profile.organization'
      },
      {
        label: '邮箱',
        value: 'profile.email'
      },
      {
        label: '角色',
        value: 'attributes.role'
      },
      {
        label: '状态',
        value: 'attributes.status'
      },
    
      // 二、DID 基础字段
      {
        label: 'DID 标识',
        value: 'id'
      },
      {
        label: '控制器',
        value: 'controller'
      }
    ]
  },

  onLoad(options) {
    const currentDid = wx.getStorageSync('currentDid') || '';
    const routeDid = options.did ? decodeURIComponent(options.did) : '';
    const routePath = options.attribute_path ? decodeURIComponent(options.attribute_path) : '';
    const routeVersion = options.version ? String(options.version) : '';

    this.setData({
      did: routeDid || currentDid,
      currentDid,
      attributePath: routePath,
      version: routeVersion
    });
  },

  onShow() {
    checkDidReachable({
      showToast: false,
      success: ({ currentDid, hasPrivateKey, documentMissing }) => {
        this.setData({
          currentDid,
          hasPrivateKey,
          did: this.data.did || currentDid,
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

  onDidInput(e) {
    this.setData({
      did: e.detail.value
    });
  },

  onVersionInput(e) {
    this.setData({
      version: e.detail.value
    });
  },

  onAttributePathInput(e) {
    this.setData({
      attributePath: e.detail.value
    });
  },

  chooseCommonAttribute(e) {
    const value = e.currentTarget.dataset.value || '';

    this.setData({
      attributePath: value
    });
  },

  useCurrentDid() {
    const currentDid = wx.getStorageSync('currentDid') || '';

    if (!currentDid) {
      wx.showToast({
        title: '当前没有已绑定 DID',
        icon: 'none'
      });
      return;
    }

    this.setData({
      did: currentDid
    });
  },

  validateForm() {
    const did = (this.data.did || '').trim();
    const attributePath = (this.data.attributePath || '').trim();
    const versionText = (this.data.version || '').trim();

    if (!did) {
      wx.showToast({
        title: '请输入 DID',
        icon: 'none'
      });
      return null;
    }

    if (!did.startsWith('did:')) {
      wx.showToast({
        title: 'DID 必须以 did: 开头',
        icon: 'none'
      });
      return null;
    }

    if (!attributePath) {
      wx.showToast({
        title: '请输入属性路径',
        icon: 'none'
      });
      return null;
    }

    if (versionText && !/^\d+$/.test(versionText)) {
      wx.showToast({
        title: '版本号必须是数字',
        icon: 'none'
      });
      return null;
    }

    const body = {
      did,
      attribute_path: attributePath
    };

    if (versionText) {
      body.version = Number(versionText);
    }

    return body;
  },

  buildProofItems(proofList) {
    if (!Array.isArray(proofList)) {
      return [];
    }

    return proofList.map((item, index) => {
      const position = item.position || item.direction || item.side || '-';
      const hash = item.hash || item.sibling_hash || item.value || '-';

      return {
        index,
        step: index + 1,
        position,
        hash,
        shortHash: this.shortHash(hash)
      };
    });
  },

  queryProof() {
    const body = this.validateForm();
    if (!body) return;
  
    this.setData({
      loading: true,
      queried: true
    });
  
    // 1. 生成属性证明前，先调用完整性验证接口
    wx.request({
      url: baseURL + '/api/did/verify',
      method: 'POST',
      header: {
        'content-type': 'application/json'
      },
      data: {
        did: body.did,
        version: body.version
      },
      success: (res) => {
        const payload = res.data || {};
  
        // 注意：HTTP 200 不代表 DID 一定可信
        // 这里必须看 payload.data.is_valid
        if (res.statusCode < 200 || res.statusCode >= 300 || payload.success === false) {
          wx.showModal({
            title: '验证失败',
            content: payload.message || '当前 DID 状态异常，请先尝试恢复。',
            confirmText: '去恢复',
            cancelText: '取消',
            success: (modalRes) => {
              if (modalRes.confirm) {
                this.goRecover(body.did, body.version);
              }
            }
          });
  
          this.setData({
            loading: false,
            result: null,
            normalized: null,
            proofItems: [],
            resultJson: ''
          });
          return;
        }
  
        const verifyData = payload.data || {};
        const isValid = verifyData.is_valid === true || verifyData.isValid === true;
  
        if (!isValid) {
          wx.showModal({
            title: 'DID 验证未通过',
            content: '检测到链上链下数据不一致，不能继续生成属性证明，请先进行数据恢复。',
            confirmText: '去恢复',
            cancelText: '取消',
            success: (modalRes) => {
              if (modalRes.confirm) {
                this.goRecover(body.did, body.version);
              }
            }
          });
  
          this.setData({
            loading: false,
            result: null,
            normalized: null,
            proofItems: [],
            resultJson: ''
          });
          return;
        }
  
        // 2. 完整性验证通过后，再生成属性证明
        this.doQueryProof(body);
      },
      fail: () => {
        wx.showToast({
          title: '验证请求失败',
          icon: 'none'
        });
  
        this.setData({
          loading: false
        });
      }
    });
  },

  doQueryProof(body) {
    wx.request({
      url: baseURL + '/api/did/proof',
      method: 'POST',
      header: {
        'content-type': 'application/json'
      },
      data: body,
      success: (res) => {
        const payload = res.data || {};
  
        if (res.statusCode < 200 || res.statusCode >= 300 || payload.success === false) {
          wx.showToast({
            title: payload.message || '证明生成失败',
            icon: 'none'
          });
  
          this.setData({
            result: null,
            normalized: null,
            proofItems: [],
            resultJson: ''
          });
          return;
        }
  
        const data = payload.data || {};
        const normalized = normalizeProofResult(data);
        const proofItems = this.buildProofItems(normalized.proofList);
  
        this.setData({
          result: data,
          normalized,
          proofItems,
          resultJson: safeJsonStringify(data)
        });
  
        wx.showToast({
          title: '证明生成成功',
          icon: 'success'
        });
      },
      fail: () => {
        wx.showToast({
          title: '无法连接后端',
          icon: 'none'
        });
  
        this.setData({
          result: null,
          normalized: null,
          proofItems: [],
          resultJson: ''
        });
      },
      complete: () => {
        this.setData({
          loading: false
        });
      }
    });
  },

  goRecover(did, version) {
    let url = `/pages/didRecover/didRecover?did=${encodeURIComponent(did)}`;
  
    if (version) {
      url += `&version=${encodeURIComponent(version)}`;
    }
  
    wx.navigateTo({
      url
    });
  },

  resetForm() {
    this.setData({
      version: '',
      attributePath: '',
      result: null,
      normalized: null,
      proofItems: [],
      resultJson: '',
      queried: false
    });
  },

  shortHash(value) {
    const text = String(value || '');
    if (text.length <= 22) return text || '-';
    return `${text.slice(0, 12)}...${text.slice(-8)}`;
  },

  formatAttributeValue(value) {
    if (value === undefined || value === null) {
      return '-';
    }

    if (typeof value === 'object') {
      return safeJsonStringify(value);
    }

    return String(value);
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

  copyResultJson() {
    if (!this.data.resultJson) {
      wx.showToast({
        title: '暂无证明结果',
        icon: 'none'
      });
      return;
    }

    wx.setClipboardData({
      data: this.data.resultJson,
      success: () => {
        wx.showToast({
          title: '证明结果已复制',
          icon: 'success'
        });
      }
    });
  },

  goLatest() {
    const did = (this.data.did || '').trim();

    if (!did) {
      wx.showToast({
        title: '请输入 DID',
        icon: 'none'
      });
      return;
    }

    wx.navigateTo({
      url: `/pages/didLatest/didLatest?did=${encodeURIComponent(did)}`
    });
  },

  goVerify() {
    const did = (this.data.did || '').trim();

    if (!did) {
      wx.showToast({
        title: '请输入 DID',
        icon: 'none'
      });
      return;
    }

    wx.navigateTo({
      url: `/pages/didVerify/didVerify?did=${encodeURIComponent(did)}`
    });
  },

  goOperation() {
    wx.switchTab({
      url: '/pages/release/release'
    });
  }
});