const ENV = 'dev'; // dev | test

const baseMap = {
  dev: 'http://127.0.0.1:5000',
  test: 'http://10.51.24.151:5000',
};

const envNameMap = {
  dev: '本地开发环境',
  test: '局域网测试环境',
};

module.exports = {
  ENV,
  baseURL: baseMap[ENV],
  envName: envNameMap[ENV],
};