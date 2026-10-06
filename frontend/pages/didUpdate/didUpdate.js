const { baseURL } = require('../../utils/config');
const {
  checkDidReady,
  checkDidController
} = require('../../utils/auth');
const { formatBeijingTime } = require('../../utils/format');

const UPDATE_API = '/api/did/update';

function getDidAuthUtils() {
  return require('../../utils/didAuth');
}

function getCryptoUtils() {
  return require('../../utils/crypto');
}

Page({
  data: {
    did: '',
    currentDid: '',
    hasPrivateKey: false,

    loading: false,
    loadingDocument: false,
    submitting: false,
    loaded: false,

    oldResult: null,
    oldChainState: null,
    oldCurrentDocument: null,

    oldUpdatedAtText: '-',

    name: '',
    publicKey: '',
    organization: '',
    email: '',
    role: 'student',
    status: 'active',

    updateResult: null,
    updateChainResult: null,
    updateTimeText: '-',

    backendOk: false
  },

  onLoad(options) {
    const currentDid = wx.getStorageSync('currentDid') || '';
    const routeDid = options.did ? decodeURIComponent(options.did) : '';

    this.setData({
      currentDid,
      did: routeDid || currentDid
    });
  },

  onShow() {
    checkDidReady({
      success: ({ currentDid, hasPrivateKey }) => {
        this.setData({
          currentDid,
          hasPrivateKey,
          did: this.data.did || currentDid
        });

        if (!this.data.loaded && this.data.did) {
          this.loadCurrentDocument();
        }
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
      loaded: false
    });

    this.loadCurrentDocument();
  },

  loadCurrentDocument() {
    const did = this.validateDid();
    if (!did) return;

    this.setData({
      loadingDocument: true,
      loading: true
    });

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
          wx.showToast({
            title: payload.message || '加载文档失败',
            icon: 'none'
          });

          this.setData({
            loaded: false,
            oldResult: null,
            oldChainState: null,
            oldCurrentDocument: null
          });

          return;
        }

        const data = payload.data || payload;
        const chainState = data.chain_state || data.chainState || {};
        const currentDocument = data.current_document || data.currentDocument || null;

        if (!currentDocument) {
          wx.showModal({
            title: '链下文档缺失',
            content: '当前 DID 的链下文档缺失，不能执行更新，请先进行数据恢复。',
            confirmText: '去恢复',
            cancelText: '取消',
            success: (modalRes) => {
              if (modalRes.confirm) {
                wx.navigateTo({
                  url: `/pages/didRecover/didRecover?did=${encodeURIComponent(did)}`
                });
              }
            }
          });

          this.setData({
            loaded: false,
            oldResult: data,
            oldChainState: chainState,
            oldCurrentDocument: null
          });

          return;
        }

        const document = currentDocument.document || currentDocument || {};
        const profile = document.profile || {};
        const attributes = document.attributes || {};

        const verificationMethod = document.verificationMethod || [];
        const firstMethod = verificationMethod[0] || {};
        const blockchainAccountId = firstMethod.blockchainAccountId || '';

        this.setData({
          loaded: true,
          oldResult: data,
          oldChainState: chainState,
          oldCurrentDocument: currentDocument,

          name: profile.name || document.name || '',
          publicKey: blockchainAccountId || document.publicKey || document.public_key || '',
          organization: profile.organization || '',
          email: profile.email || '',
          role: attributes.role || 'student',
          status: attributes.status || currentDocument.status || 'active',

          oldUpdatedAtText: formatBeijingTime(
            currentDocument.updated_at ||
            currentDocument.updatedAt ||
            chainState.updated_at ||
            chainState.updatedAt
          )
        });

        wx.showToast({
          title: '文档已加载',
          icon: 'success'
        });
      },
      fail: () => {
        wx.showToast({
          title: '网络请求失败',
          icon: 'none'
        });
      },
      complete: () => {
        this.setData({
          loading: false,
          loadingDocument: false
        });

        this.checkBackend();
      }
    });
  },

  validateForm() {
    const did = this.validateDid();
    if (!did) return '';

    if (!this.data.loaded || !this.data.oldCurrentDocument) {
      wx.showToast({
        title: '请先加载当前文档',
        icon: 'none'
      });
      return '';
    }

    if (!this.data.name.trim()) {
      wx.showToast({
        title: '姓名不能为空',
        icon: 'none'
      });
      return '';
    }

    if (!this.data.role.trim()) {
      wx.showToast({
        title: '角色不能为空',
        icon: 'none'
      });
      return '';
    }

    if (!this.data.status.trim()) {
      wx.showToast({
        title: '状态不能为空',
        icon: 'none'
      });
      return '';
    }

    return did;
  },

  buildUpdatedDocument(did) {
    const oldCurrentDocument = this.data.oldCurrentDocument || {};
    const oldDocument = oldCurrentDocument.document || oldCurrentDocument || {};
    const oldProfile = oldDocument.profile || {};
    const oldAttributes = oldDocument.attributes || {};

    const updatedDocument = {
      ...oldDocument,
      id: did,
      controller: oldDocument.controller || did,
      verificationMethod: oldDocument.verificationMethod || [],
      authentication: oldDocument.authentication || [],

      profile: {
        ...oldProfile,
        name: this.data.name.trim(),
        organization: this.data.organization.trim(),
        email: this.data.email.trim()
      },

      attributes: {
        ...oldAttributes,
        role: this.data.role.trim(),
        status: this.data.status.trim()
      }
    };

    /**
     * 兼容旧 DID 文档。
     * 如果旧文档原来有 name / publicKey，保留可展示字段。
     */
    if (Object.prototype.hasOwnProperty.call(oldDocument, 'name')) {
      updatedDocument.name = this.data.name.trim();
    }

    if (Object.prototype.hasOwnProperty.call(oldDocument, 'publicKey')) {
      updatedDocument.publicKey = oldDocument.publicKey;
    }

    return updatedDocument;
  },

  submitUpdate() {
    const did = this.validateForm();
    if (!did) return;

    checkDidController({
      did,
      success: () => {
        const document = this.buildUpdatedDocument(did);

        wx.showModal({
          title: '确认更新 DID',
          content: '提交后将生成新的 DID 文档版本，并更新链上可信状态。是否继续？',
          confirmText: '更新',
          confirmColor: '#4C8DFF',
          cancelText: '取消',
          success: (modalRes) => {
            if (!modalRes.confirm) return;

            this.doSubmitUpdate(did, document);
          }
        });
      }
    });
  },

  async doSubmitUpdate(did, document) {
    this.setData({
      submitting: true,
      loading: true
    });

    try {
      const { buildDidAuthWithPrivateKey } = getDidAuthUtils();
      const { getDidPrivateKey } = getCryptoUtils();

      const privateKey = getDidPrivateKey(did);

      if (!privateKey) {
        throw new Error('当前设备没有该 DID 私钥');
      }

      const auth = await buildDidAuthWithPrivateKey({
        did,
        operation: 'update',
        privateKey
      });

      wx.request({
        url: baseURL + UPDATE_API,
        method: 'POST',
        data: {
          did,
          document,
          auth
        },
        header: {
          'content-type': 'application/json'
        },
        success: (res) => {
          const payload = res.data || {};

          if (res.statusCode < 200 || res.statusCode >= 300 || payload.success === false) {
            wx.showToast({
              title: payload.message || 'DID更新失败',
              icon: 'none'
            });
            return;
          }

          const data = payload.data || payload;
          const chainResult =
            data.chain_result ||
            data.chainResult ||
            data.transaction ||
            data.tx ||
            null;

          this.setData({
            updateResult: data,
            updateChainResult: chainResult,
            updateTimeText: formatBeijingTime(Date.now()),
            loaded: false
          });

          wx.showToast({
            title: 'DID更新成功',
            icon: 'success'
          });

          setTimeout(() => {
            this.loadCurrentDocument();
          }, 600);
        },
        fail: () => {
          wx.showToast({
            title: '网络请求失败',
            icon: 'none'
          });
        },
        complete: () => {
          this.setData({
            submitting: false,
            loading: false
          });

          this.checkBackend();
        }
      });
    } catch (e) {
      this.setData({
        submitting: false,
        loading: false
      });

      wx.showToast({
        title: e.message || '更新签名失败',
        icon: 'none'
      });
    }
  },

  resetForm() {
    if (!this.data.oldCurrentDocument) {
      wx.showToast({
        title: '暂无原始文档',
        icon: 'none'
      });
      return;
    }

    const document = this.data.oldCurrentDocument.document || this.data.oldCurrentDocument || {};
    const profile = document.profile || {};
    const attributes = document.attributes || {};
    const verificationMethod = document.verificationMethod || [];
    const firstMethod = verificationMethod[0] || {};
    const blockchainAccountId = firstMethod.blockchainAccountId || '';

    this.setData({
      name: profile.name || document.name || '',
      publicKey: blockchainAccountId || document.publicKey || document.public_key || '',
      organization: profile.organization || '',
      email: profile.email || '',
      role: attributes.role || 'student',
      status: attributes.status || this.data.oldCurrentDocument.status || 'active'
    });

    wx.showToast({
      title: '已恢复原值',
      icon: 'success'
    });
  },

  copyDocumentHash() {
    const value = this.getDocumentHash();

    if (!value) {
      wx.showToast({
        title: '暂无文档摘要',
        icon: 'none'
      });
      return;
    }

    this.copyText(value, '文档摘要已复制');
  },

  copyTransactionHash() {
    const data = this.data.updateResult || {};
    const chainResult = this.data.updateChainResult || {};

    const value =
      data.transaction_hash ||
      data.tx_hash ||
      data.transactionHash ||
      chainResult.transaction_hash ||
      chainResult.tx_hash ||
      chainResult.transactionHash ||
      '';

    if (!value) {
      wx.showToast({
        title: '暂无交易哈希',
        icon: 'none'
      });
      return;
    }

    this.copyText(value, '交易哈希已复制');
  },

  copyText(value, message) {
    const text = String(value || '');

    if (!text) {
      wx.showToast({
        title: '暂无内容可复制',
        icon: 'none'
      });
      return;
    }

    wx.setClipboardData({
      data: text,
      success: () => {
        wx.showToast({
          title: message || '已复制',
          icon: 'success'
        });
      }
    });
  },

  getDocumentHash() {
    const data = this.data.updateResult || {};
    const chainResult = this.data.updateChainResult || {};
    const oldChainState = this.data.oldChainState || {};
    const oldCurrentDocument = this.data.oldCurrentDocument || {};

    return (
      data.document_hash ||
      data.doc_hash ||
      data.docHash ||
      chainResult.document_hash ||
      chainResult.doc_hash ||
      oldChainState.document_hash ||
      oldChainState.doc_hash ||
      oldCurrentDocument.document_hash ||
      oldCurrentDocument.doc_hash ||
      ''
    );
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