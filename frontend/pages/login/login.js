const { baseURL } = require('../../utils/config');
const { setCurrentDid } = require('../../utils/auth');

const HOME_URL = '/pages/index/index';

/**
 * 加密相关模块懒加载。
 *
 * 不要在文件顶部直接 require('../../utils/crypto')。
 * elliptic/js-sha3 初始化较重，顶部加载容易导致微信模拟器页面启动卡顿。
 */
function getCryptoUtils() {
  return require('../../utils/crypto');
}

function getDidDocumentUtils() {
  return require('../../utils/didDocument');
}

function getDidAuthUtils() {
  return require('../../utils/didAuth');
}

/**
 * 给主线程一次 UI 渲染机会，避免点击后立即进行重计算导致模拟器无响应。
 */
function nextTickDelay(delay = 50) {
  return new Promise((resolve) => {
    setTimeout(resolve, delay);
  });
}

/**
 * Promise 版 wx.request。
 */
function request(options) {
  return new Promise((resolve, reject) => {
    wx.request({
      ...options,
      success: (res) => {
        const payload = res.data || {};

        if (res.statusCode < 200 || res.statusCode >= 300 || payload.success === false) {
          reject(new Error(payload.message || payload.error || '请求失败'));
          return;
        }

        resolve(payload.data || payload);
      },
      fail: () => {
        reject(new Error('网络请求失败'));
      }
    });
  });
}

Page({
  data: {
    // 1 = 导入已有 DID，0 = 创建新 DID
    current: 1,

    // 导入已有 DID
    bindDid: '',
    importPrivateKey: '',

    // 创建新 DID
    // registerDid / publicKey 仅用于页面展示自动生成结果
    registerDid: '',
    name: '',
    publicKey: '',
    organization: '',
    email: '',
    role: 'student',

    // 图形验证码
    imgCode: '',
    captcha: '',

    loading: false,
    latestResult: null,
    registerResult: null
  },

  /**
   * 切换入口。
   */
  click(e) {
    if (this.data.loading) return;

    const index = Number(e.currentTarget.dataset.code);

    this.setData({
      current: index,
      imgCode: '',
      latestResult: null,
      registerResult: null
    });

    this.drawCaptcha();
  },

  /**
   * 通用输入绑定。
   */
  onInput(e) {
    const field = e.currentTarget.dataset.field;

    this.setData({
      [field]: e.detail.value
    });
  },

  /**
   * 校验 DID。
   */
  validateDid(did) {
    const value = (did || '').trim();

    if (!value) {
      wx.showToast({
        title: 'DID不能为空',
        icon: 'none'
      });
      return '';
    }

    if (!value.startsWith('did:ethr:')) {
      wx.showToast({
        title: 'DID必须为did:ethr格式',
        icon: 'none'
      });
      return '';
    }

    const address = value.slice('did:ethr:'.length);

    if (!address.startsWith('0x') || address.length !== 42) {
      wx.showToast({
        title: 'DID地址格式错误',
        icon: 'none'
      });
      return '';
    }

    return value;
  },

  /**
   * 校验图形验证码。
   */
  validateCaptcha() {
    const input = (this.data.imgCode || '').trim();
    const captcha = (this.data.captcha || '').trim();

    if (!input) {
      wx.showToast({
        title: '验证码不能为空',
        icon: 'none'
      });
      return false;
    }

    if (input.toLowerCase() !== captcha.toLowerCase()) {
      wx.showToast({
        title: '验证码不一致',
        icon: 'none'
      });

      this.setData({
        imgCode: ''
      });

      this.drawCaptcha();
      return false;
    }

    return true;
  },

  /**
   * 校验创建 DID 的身份资料。
   */
  validateRegisterForm() {
    if (!this.data.name.trim()) {
      wx.showToast({
        title: '姓名不能为空',
        icon: 'none'
      });
      return false;
    }

    if (!this.data.organization.trim()) {
      wx.showToast({
        title: '组织不能为空',
        icon: 'none'
      });
      return false;
    }

    if (!this.data.email.trim()) {
      wx.showToast({
        title: '邮箱不能为空',
        icon: 'none'
      });
      return false;
    }

    const email = this.data.email.trim();

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      wx.showToast({
        title: '邮箱格式错误',
        icon: 'none'
      });
      return false;
    }

    if (!this.data.role.trim()) {
      wx.showToast({
        title: '角色不能为空',
        icon: 'none'
      });
      return false;
    }

    return true;
  },

  /**
   * 生成图形验证码。
   */
  drawCaptcha() {
    const query = wx.createSelectorQuery();
    const that = this;

    query
      .select('#captchaCanvas')
      .fields({
        node: true,
        size: true
      })
      .exec((res) => {
        if (!res || !res[0] || !res[0].node) {
          return;
        }

        const canvas = res[0].node;
        const ctx = canvas.getContext('2d');
        const { pixelRatio } = wx.getWindowInfo();
        const dpr = pixelRatio || 1;

        const width = res[0].width || 120;
        const height = res[0].height || 40;

        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.scale(dpr, dpr);

        const letters = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789';
        let captcha = '';

        for (let i = 0; i < 4; i++) {
          captcha += letters.charAt(Math.floor(Math.random() * letters.length));
        }

        that.setData({
          captcha
        });

        ctx.fillStyle = '#1E222B';
        ctx.fillRect(0, 0, width, height);

        for (let i = 0; i < 20; i++) {
          ctx.fillStyle = that.randomColor(55, 110);
          ctx.beginPath();
          ctx.arc(Math.random() * width, Math.random() * height, 1.2, 0, Math.PI * 2);
          ctx.fill();
        }

        for (let i = 0; i < captcha.length; i++) {
          ctx.save();
          ctx.fillStyle = i % 2 === 0 ? '#4C8DFF' : '#38BDF8';
          ctx.font = 'bold 20px serif';
          ctx.translate(16 + i * 20, 26);
          ctx.rotate((Math.random() - 0.5) * 0.35);
          ctx.fillText(captcha[i], 0, 0);
          ctx.restore();
        }

        for (let j = 0; j < 8; j++) {
          ctx.strokeStyle = that.randomColor(70, 150);
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(Math.random() * width, Math.random() * height);
          ctx.lineTo(Math.random() * width, Math.random() * height);
          ctx.stroke();
        }
      });
  },

  /**
   * 刷新验证码。
   */
  changeImg() {
    if (this.data.loading) return;

    this.setData({
      imgCode: ''
    });

    this.drawCaptcha();
  },

  /**
   * 随机颜色。
   */
  randomColor(min, max) {
    const r = Math.floor(Math.random() * (max - min) + min);
    const g = Math.floor(Math.random() * (max - min) + min);
    const b = Math.floor(Math.random() * (max - min) + min);

    return `rgb(${r},${g},${b})`;
  },

  /**
   * 统一进入首页。
   */
  goHome() {
    wx.switchTab({
      url: HOME_URL
    });
  },

  /**
   * 设置 loading。
   */
  startLoading(title = '处理中...') {
    this.setData({
      loading: true
    });

    wx.showLoading({
      title,
      mask: true
    });
  },

  /**
   * 结束 loading。
   */
  stopLoading() {
    this.setData({
      loading: false
    });

    wx.hideLoading();
  },

  /**
   * 导入已有 DID。
   *
   * 逻辑：
   * 1. 用户输入 DID + 私钥
   * 2. 本地校验私钥能否推出 DID 地址
   * 3. 请求 bind challenge
   * 4. 用私钥签名
   * 5. 调用 /api/did/bind
   * 6. 后端验签通过后，保存 currentDid 和本地私钥
   */
  async bindExistingDid() {
    const did = this.validateDid(this.data.bindDid);
    if (!did) return;

    const privateKey = (this.data.importPrivateKey || '').trim();

    if (!privateKey) {
      wx.showToast({
        title: '请输入DID私钥',
        icon: 'none'
      });
      return;
    }

    if (!this.validateCaptcha()) return;

    this.startLoading('正在导入...');

    try {
      await nextTickDelay();

      const {
        validatePrivateKeyForDid,
        saveDidPrivateKey
      } = getCryptoUtils();

      const {
        buildDidAuthWithPrivateKey
      } = getDidAuthUtils();

      const privateKeyMatched = validatePrivateKeyForDid(did, privateKey);

      if (!privateKeyMatched) {
        throw new Error('私钥与DID不匹配');
      }

      await nextTickDelay();

      const auth = await buildDidAuthWithPrivateKey({
        did,
        operation: 'bind',
        privateKey
      });

      const data = await request({
        url: baseURL + '/api/did/bind',
        method: 'POST',
        header: {
          'content-type': 'application/json'
        },
        data: {
          did,
          auth
        }
      });

      saveDidPrivateKey(did, privateKey);
      setCurrentDid(did, data);

      this.setData({
        latestResult: data,
        imgCode: ''
      });

      wx.showToast({
        title: '导入成功',
        icon: 'success',
        duration: 800
      });

      setTimeout(() => {
        this.goHome();
      }, 800);
    } catch (e) {
      wx.showToast({
        title: e.message || '导入失败',
        icon: 'none'
      });

      this.setData({
        imgCode: ''
      });

      this.drawCaptcha();
    } finally {
      this.stopLoading();
    }
  },

  /**
   * 创建新 DID。
   *
   * 逻辑：
   * 1. 用户只输入身份资料
   * 2. 小程序生成 privateKey/address/DID
   * 3. 小程序构造 DID Document
   * 4. 请求 register challenge
   * 5. 用私钥签名
   * 6. 调用 /api/did/register
   * 7. 后端验签、注册、写链、保存恢复块
   * 8. 小程序保存 DID 和私钥
   */
  async registerDidAccount() {
    if (!this.validateRegisterForm()) return;
    if (!this.validateCaptcha()) return;

    this.startLoading('正在创建...');

    let keyPair = null;

    try {
      await nextTickDelay();

      const {
        createDidKeyPair,
        saveDidPrivateKey
      } = getCryptoUtils();

      const {
        buildDidDocument
      } = getDidDocumentUtils();

      const {
        buildDidAuthWithPrivateKey
      } = getDidAuthUtils();

      keyPair = await createDidKeyPair();

      this.setData({
        registerDid: keyPair.did,
        publicKey: keyPair.address
      });

      await nextTickDelay();

      const document = buildDidDocument({
        did: keyPair.did,
        address: keyPair.address,
        name: this.data.name.trim(),
        email: this.data.email.trim(),
        organization: this.data.organization.trim(),
        role: this.data.role.trim() || 'student',
        status: 'active'
      });

      const auth = await buildDidAuthWithPrivateKey({
        did: keyPair.did,
        operation: 'register',
        privateKey: keyPair.privateKey
      });

      const data = await request({
        url: baseURL + '/api/did/register',
        method: 'POST',
        header: {
          'content-type': 'application/json'
        },
        data: {
          did: keyPair.did,
          document,
          auth
        }
      });

      saveDidPrivateKey(keyPair.did, keyPair.privateKey);
      setCurrentDid(keyPair.did, data);

      this.setData({
        registerResult: data,
        imgCode: ''
      });

      this.stopLoading();

      wx.showModal({
        title: 'DID创建成功',
        content: `DID 已创建成功。\n\n请立即复制并妥善备份你的控制私钥。私钥丢失后无法更新或恢复该 DID。\n\nDID：${keyPair.did}`,
        confirmText: '复制私钥',
        showCancel: false,
        success: () => {
          wx.setClipboardData({
            data: keyPair.privateKey,
            success: () => {
              wx.showToast({
                title: '私钥已复制',
                icon: 'success'
              });
      
              this.goHome();
            },
            fail: () => {
              wx.showToast({
                title: '复制失败，请重试',
                icon: 'none'
              });
            }
          });
        }
      });
    } catch (e) {
      this.stopLoading();

      wx.showToast({
        title: e.message || 'DID创建失败',
        icon: 'none'
      });

      this.setData({
        imgCode: '',
        registerDid: keyPair ? keyPair.did : this.data.registerDid,
        publicKey: keyPair ? keyPair.address : this.data.publicKey
      });

      this.drawCaptcha();
    }
  },

  /**
   * 主按钮。
   *
   * 这里先 showLoading，再延迟执行具体逻辑，
   * 避免模拟器点击后立即进行加密计算导致 UI 卡死。
   */
  async submit() {
    if (this.data.loading) return;

    await nextTickDelay();

    if (this.data.current === 1) {
      this.bindExistingDid();
    } else {
      this.registerDidAccount();
    }
  },

  /**
   * 填充演示数据。
   *
   * 创建 DID 时，DID 和控制地址不再手填，只展示“自动生成”。
   * 导入 DID 时，必须输入真实 DID + 对应私钥。
   */
  fillDemoDid() {
    if (this.data.loading) return;

    const suffix = Date.now().toString().slice(-6);

    if (this.data.current === 1) {
      this.setData({
        bindDid: '',
        importPrivateKey: '',
        imgCode: ''
      });

      wx.showToast({
        title: '请填写真实DID和私钥',
        icon: 'none'
      });
    } else {
      this.setData({
        registerDid: '自动生成',
        name: `用户${suffix}`,
        publicKey: '自动生成',
        organization: 'Nanjing Institute of Technology',
        email: `user${suffix}@example.com`,
        role: 'student',
        imgCode: ''
      });
    }

    this.drawCaptcha();
  },

  onLoad() {},

  onReady() {
    this.drawCaptcha();
  },

  onShow() {
    wx.hideHomeButton();
  }
});