/**
 * 将后端返回的时间统一格式化为北京时间中文格式
 *
 * 支持：
 * 1. Unix 秒级时间戳：1778079198
 * 2. Unix 毫秒级时间戳：1778079198000
 * 3. GMT / UTC 字符串：Wed, 06 May 2026 14:53:18 GMT
 * 4. ISO 字符串
 *
 * 输出示例：
 * 2026年05月06日 22:53:18
 */
function formatBeijingTime(value) {
  if (value === undefined || value === null || value === '') {
    return '-';
  }

  let date;

  if (typeof value === 'number' || /^\d+$/.test(String(value))) {
    const num = Number(value);
    date = new Date(num < 1000000000000 ? num * 1000 : num);
  } else {
    date = new Date(value);
  }

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  const beijingTime = new Date(date.getTime() + 8 * 60 * 60 * 1000);

  const year = beijingTime.getUTCFullYear();
  const month = String(beijingTime.getUTCMonth() + 1).padStart(2, '0');
  const day = String(beijingTime.getUTCDate()).padStart(2, '0');
  const hour = String(beijingTime.getUTCHours()).padStart(2, '0');
  const minute = String(beijingTime.getUTCMinutes()).padStart(2, '0');
  const second = String(beijingTime.getUTCSeconds()).padStart(2, '0');

  return `${year}年${month}月${day}日 ${hour}:${minute}:${second}`;
}

/**
 * 简短时间格式
 * 输出示例：
 * 05月06日 22:53
 */
function formatBeijingTimeShort(value) {
  const full = formatBeijingTime(value);

  if (full === '-' || !full.includes('年')) {
    return full;
  }

  return full.replace(/^\d{4}年/, '').replace(/:\d{2}$/, '');
}

module.exports = {
  formatBeijingTime,
  formatBeijingTimeShort
};