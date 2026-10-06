const {
  checkDidReachable,
  verifyDidIntegrityOrRecover
} = require('../../utils/auth');

Page({
  data: {
    currentDid: '',
    hasPrivateKey: false,
    documentMissing: false,
    loading: false,

    quickActions: [
      {
        key: 'latest',
        title: '状态查询',
        desc: '查看链上状态与链下当前文档',
        icon: 'search',
        colorClass: 'blue'
      },
      {
        key: 'update',
        title: 'DID 更新',
        desc: '修改 DID 文档属性并写入新版本',
        icon: 'edit-1',
        colorClass: 'cyan'
      },
      {
        key: 'verify',
        title: '身份认证',
        desc: '校验文档摘要、默克尔根和版本哈希链',
        icon: 'check-circle',
        colorClass: 'green'
      },
      {
        key: 'recover',
        title: '数据恢复',
        desc: '恢复链下异常或丢失的 DID 文档',
        icon: 'refresh',
        colorClass: 'orange'
      },
      {
        key: 'proof',
        title: '属性证明',
        desc: '生成属性级默克尔证明',
        icon: 'secured',
        colorClass: 'purple',
        wide: true
      }
    ]
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 'release',
        value: '/pages/release/release'
      });
    }

    this.loadDidStatus();
  },

  loadDidStatus() {
    this.setData({
      loading: true
    });

    checkDidReachable({
      success: ({ currentDid, hasPrivateKey, documentMissing }) => {
        this.setData({
          currentDid,
          hasPrivateKey,
          documentMissing,
          loading: false
        });
      },
      fail: () => {
        this.setData({
          currentDid: '',
          hasPrivateKey: false,
          documentMissing: false,
          loading: false
        });
      }
    });
  },

  handleQuickAction(e) {
    const key = e.currentTarget.dataset.key;

    if (!key) {
      wx.showToast({
        title: '功能参数缺失',
        icon: 'none'
      });
      return;
    }

    if (!this.data.currentDid) {
      wx.showToast({
        title: '请先创建或导入DID',
        icon: 'none'
      });
      return;
    }

    /**
     * 链下 current_document 缺失时：
     * 只允许状态查询和数据恢复。
     */
    if (this.data.documentMissing && key !== 'latest' && key !== 'recover') {
      wx.showModal({
        title: '链下文档缺失',
        content: '当前 DID 的链下文档缺失，请先进行数据恢复。',
        confirmText: '去恢复',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            wx.navigateTo({
              url: `/pages/didRecover/didRecover?did=${encodeURIComponent(this.data.currentDid)}`
            });
          }
        }
      });
      return;
    }

    /**
     * 没有本地 DID 私钥时：
     * 不允许更新和恢复。
     *
     * verify/proof/latest 是公开验证类操作，可以不要求私钥。
     */
    if (!this.data.hasPrivateKey && (key === 'update' || key === 'recover')) {
      wx.showModal({
        title: '缺少DID私钥',
        content: '当前设备没有该 DID 的控制私钥，无法执行更新或恢复。请先在登录页导入已有 DID 及其私钥。',
        confirmText: '去导入',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            wx.reLaunch({
              url: '/pages/login/login'
            });
          }
        }
      });
      return;
    }

    const routeMap = {
      latest: '/pages/didLatest/didLatest',
      update: '/pages/didUpdate/didUpdate',
      verify: '/pages/didVerify/didVerify',
      recover: '/pages/didRecover/didRecover',
      proof: '/pages/didProof/didProof'
    };

    const url = routeMap[key];

    if (!url) {
      wx.showToast({
        title: '功能暂不可用',
        icon: 'none'
      });
      return;
    }

    if (key === 'recover') {
      wx.navigateTo({
        url: `${url}?did=${encodeURIComponent(this.data.currentDid)}`
      });
      return;
    }

    wx.navigateTo({
      url
    });
  }
});