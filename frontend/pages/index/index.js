const { baseURL } = require('../../utils/config');
const {
  checkDidReachable,
  clearDidSession
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
    loading: false
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 'index',
        value: '/pages/index/index'
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

  copyDid() {
    if (!this.data.currentDid) {
      wx.showToast({
        title: '暂无DID可复制',
        icon: 'none'
      });
      return;
    }

    wx.setClipboardData({
      data: this.data.currentDid,
      success: () => {
        wx.showToast({
          title: 'DID已复制',
          icon: 'success'
        });
      }
    });
  },
  
  copyCurrentDid() {
    const did = this.data.currentDid || '';
  
    if (!did) {
      wx.showToast({
        title: '暂无 DID 可复制',
        icon: 'none'
      });
      return;
    }
  
    wx.setClipboardData({
      data: did,
      success: () => {
        wx.showToast({
          title: 'DID 已复制',
          icon: 'success'
        });
      }
    });
  },

  unbindDid() {
    wx.showModal({
      title: '解除绑定',
      content: '确定要解除当前 DID 绑定吗？解除后需要重新导入或创建 DID 才能继续使用系统。本操作不会删除本地私钥。',
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
  }
});