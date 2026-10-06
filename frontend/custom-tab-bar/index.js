Component({
  data: {
    value: '/pages/index/index',

    tabBarList: [
      {
        value: '/pages/index/index',
        label: '首页',
        icon: 'home'
      },
      {
        value: '/pages/release/release',
        label: '操作',
        icon: 'app'
      },
      {
        value: '/pages/my/my',
        label: '我的',
        icon: 'user'
      }
    ]
  },

  methods: {
    onChange(e) {
      const url = e.detail.value;

      wx.switchTab({
        url
      });
    }
  }
});