const { baseURL, envName } = require('../../utils/config');
const {
  checkDidReachable,
  clearDidSession,
  clearDidSessionWithPrivateKey
} = require('../../utils/auth');

Page({
  data: {
    currentDid: '',
    hasPrivateKey: false,

    didInfo: null,
    chainState: null,
    currentDocument: null,
    documentMissing: false,

    backendOk: false,
    loading: false,

    baseURL,

    identityMode: 'DID 控制私钥模式',
    authMode: 'Challenge 签名 + 链上摘要 + 链下文档校验',
    appMode: envName
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 'my',
        value: '/pages/my/my'
      });
    }

    this.checkBackend();
    this.loadCurrentDid();
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

  loadCurrentDid() {
    this.setData({
      loading: true
    });

    checkDidReachable({
      success: ({
        currentDid,
        hasPrivateKey,
        didInfo,
        chainState,
        currentDocument,
        documentMissing
      }) => {
        this.setData({
          currentDid,
          hasPrivateKey,
          didInfo,
          chainState,
          currentDocument,
          documentMissing,
          loading: false
        });
      },
      fail: () => {
        this.setData({
          currentDid: '',
          hasPrivateKey: false,
          didInfo: null,
          chainState: null,
          currentDocument: null,
          documentMissing: false,
          loading: false
        });
      }
    });
  },

  refreshCurrentDid() {
    this.checkBackend();
    this.loadCurrentDid();

    wx.showToast({
      title: '正在刷新',
      icon: 'none'
    });
  },

  copyDid() {
    if (!this.data.currentDid) {
      wx.showToast({
        title: '暂无DID可复制',
        icon: 'none'
      });
      return;
    }

    this.copyText(this.data.currentDid, 'DID已复制');
  },

  copyPrivateKeyStatus() {
    const text = this.data.hasPrivateKey ? '本机已保存DID控制私钥' : '本机未保存DID控制私钥';

    this.copyText(text, '私钥状态已复制');
  },

  copyDocumentHash() {
    const value =
      this.data.chainState?.document_hash ||
      this.data.chainState?.doc_hash ||
      this.data.currentDocument?.document_hash ||
      this.data.currentDocument?.doc_hash ||
      '';

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
    const value =
      this.data.chainState?.merkle_root ||
      this.data.currentDocument?.merkle_root ||
      '';

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
    const value =
      this.data.chainState?.version_hash ||
      this.data.currentDocument?.version_hash ||
      '';

    if (!value) {
      wx.showToast({
        title: '暂无版本哈希',
        icon: 'none'
      });
      return;
    }

    this.copyText(value, '版本哈希已复制');
  },

  copyText(text, message) {
    wx.setClipboardData({
      data: String(text),
      success: () => {
        wx.showToast({
          title: message || '已复制',
          icon: 'success'
        });
      }
    });
  },

  goRecover() {
    const did = this.data.currentDid;

    if (!did) {
      wx.showToast({
        title: '暂无DID',
        icon: 'none'
      });
      return;
    }

    wx.navigateTo({
      url: `/pages/didRecover/didRecover?did=${encodeURIComponent(did)}`
    });
  },

  goLatest() {
    wx.navigateTo({
      url: '/pages/didLatest/didLatest'
    });
  },

  goOperation() {
    wx.switchTab({
      url: '/pages/release/release'
    });
  },

  unbindDid() {
    wx.showModal({
      title: '解除 DID 绑定',
      content: '确定要解除当前 DID 绑定吗？本操作只清除当前绑定状态，不删除本地私钥。之后可重新导入或切换 DID。',
      confirmText: '解除',
      confirmColor: '#EF4444',
      cancelText: '取消',
      success: (res) => {
        if (!res.confirm) return;

        clearDidSession();

        wx.showToast({
          title: '已解除绑定',
          icon: 'success',
          duration: 800
        });

        setTimeout(() => {
          wx.reLaunch({
            url: '/pages/login/login'
          });
        }, 800);
      }
    });
  },

  deleteLocalIdentity() {
    if (!this.data.currentDid) {
      wx.showToast({
        title: '暂无DID',
        icon: 'none'
      });
      return;
    }

    wx.showModal({
      title: '删除本地私钥',
      content: '这会删除当前 DID 的本地控制私钥。若未备份私钥，将无法更新或恢复该 DID。确定继续吗？',
      confirmText: '删除',
      confirmColor: '#EF4444',
      cancelText: '取消',
      success: (res) => {
        if (!res.confirm) return;

        clearDidSessionWithPrivateKey();

        wx.showToast({
          title: '本地身份已删除',
          icon: 'success',
          duration: 800
        });

        setTimeout(() => {
          wx.reLaunch({
            url: '/pages/login/login'
          });
        }, 800);
      }
    });
  },

  goLogin() {
    wx.showModal({
      title: '切换 DID',
      content: '切换 DID 会清除当前本地绑定信息，但不会删除本地私钥。是否继续？',
      confirmText: '继续',
      confirmColor: '#4C8DFF',
      cancelText: '取消',
      success: (res) => {
        if (!res.confirm) return;

        clearDidSession();

        wx.reLaunch({
          url: '/pages/login/login'
        });
      }
    });
  }
});