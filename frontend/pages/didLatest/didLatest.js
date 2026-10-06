const { baseURL } = require('../../utils/config');
const { checkDidReachable } = require('../../utils/auth');
const { formatBeijingTime } = require('../../utils/format');

Page({
  data: {
    did: '',
    currentDid: '',
    hasPrivateKey: false,
    documentMissing: false,

    loading: false,
    queried: false,

    result: null,
    chainState: null,
    currentDocument: null,
    documentJson: '',

    chainUpdatedAtText: '-',
    documentCreatedAtText: '-',
    documentUpdatedAtText: '-',

    backendOk: false
  },

  onLoad(options) {
    const currentDid = wx.getStorageSync('currentDid') || '';
    const routeDid = options.did ? decodeURIComponent(options.did) : '';

    this.setData({
      did: routeDid || currentDid,
      currentDid
    });
  },

  onShow() {
    checkDidReachable({
      success: ({ currentDid, hasPrivateKey, documentMissing }) => {
        this.setData({
          currentDid,
          hasPrivateKey,
          did: this.data.did || currentDid,
          documentMissing
        });

        if (!this.data.queried && this.data.did) {
          this.queryLatest();
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

  onDidInput(e) {
    this.setData({
      did: e.detail.value
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

  queryLatest() {
    const did = this.validateDid();
    if (!did) return;

    this.setData({
      loading: true,
      queried: true
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
            title: payload.message || '查询失败',
            icon: 'none'
          });

          this.setData({
            result: null,
            chainState: null,
            currentDocument: null,
            documentMissing: false,
            documentJson: '',
            chainUpdatedAtText: '-',
            documentCreatedAtText: '-',
            documentUpdatedAtText: '-'
          });

          return;
        }

        const data = payload.data || payload;
        const chainState = data.chain_state || data.chainState || {};
        const currentDocument = data.current_document || data.currentDocument || null;
        const documentMissing = !currentDocument;

        let documentJson = '';

        if (currentDocument) {
          const document = currentDocument.document || currentDocument;

          try {
            documentJson = JSON.stringify(document, null, 2);
          } catch (e) {
            documentJson = String(document);
          }
        }

        this.setData({
          result: data,
          chainState,
          currentDocument,
          documentMissing,
          documentJson,

          chainUpdatedAtText: formatBeijingTime(
            chainState.updated_at || chainState.updatedAt
          ),
          documentCreatedAtText: formatBeijingTime(
            currentDocument && (currentDocument.created_at || currentDocument.createdAt)
          ),
          documentUpdatedAtText: formatBeijingTime(
            currentDocument && (currentDocument.updated_at || currentDocument.updatedAt)
          )
        });

        wx.showToast({
          title: documentMissing ? '链下文档缺失' : '查询成功',
          icon: documentMissing ? 'none' : 'success'
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
          loading: false
        });

        this.checkBackend();
      }
    });
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
      did: currentDid
    });

    this.queryLatest();
  },

  goRecover() {
    const did = this.validateDid();
    if (!did) return;

    wx.navigateTo({
      url: `/pages/didRecover/didRecover?did=${encodeURIComponent(did)}`
    });
  },

  copyDid() {
    this.copyText(this.data.did, 'DID已复制');
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

  copyMerkleRoot() {
    const value = this.getMerkleRoot();

    if (!value) {
      wx.showToast({
        title: '暂无默克尔根',
        icon: 'none'
      });
      return;
    }

    this.copyText(value, '默克尔根已复制');
  },

  copyVersionHash() {
    const value = this.getVersionHash();

    if (!value) {
      wx.showToast({
        title: '暂无版本哈希',
        icon: 'none'
      });
      return;
    }

    this.copyText(value, '版本哈希已复制');
  },

  copyDocumentJson() {
    if (!this.data.documentJson) {
      wx.showToast({
        title: '暂无文档内容',
        icon: 'none'
      });
      return;
    }

    this.copyText(this.data.documentJson, 'DID文档已复制');
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
    const chainState = this.data.chainState || {};
    const currentDocument = this.data.currentDocument || {};

    return (
      chainState.document_hash ||
      chainState.doc_hash ||
      currentDocument.document_hash ||
      currentDocument.doc_hash ||
      ''
    );
  },

  getMerkleRoot() {
    const chainState = this.data.chainState || {};
    const currentDocument = this.data.currentDocument || {};

    return (
      chainState.merkle_root ||
      chainState.status_root ||
      currentDocument.merkle_root ||
      currentDocument.status_root ||
      ''
    );
  },

  getVersionHash() {
    const chainState = this.data.chainState || {};
    const currentDocument = this.data.currentDocument || {};

    return (
      chainState.version_hash ||
      chainState.vh_latest ||
      currentDocument.version_hash ||
      currentDocument.vh_latest ||
      ''
    );
  },

  goOperation() {
    wx.switchTab({
      url: '/pages/release/release'
    });
  }
});