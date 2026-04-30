const express = require('express');
const router = express.Router();
const https = require('https');
const { login } = require('../db');

const APP_ID = process.env.WX_APP_ID || '';
const APP_SECRET = process.env.WX_APP_SECRET || '';

router.post('/login', (req, res) => {
  const { code } = req.body;
  if (!code) {
    return res.status(400).json({ error: '缺少登录凭证' });
  }

  if (!APP_ID || !APP_SECRET) {
    return res.status(500).json({ error: '服务器未配置微信小程序 AppID 和 AppSecret' });
  }

  const url = `https://api.weixin.qq.com/sns/jscode2session?appid=${APP_ID}&secret=${APP_SECRET}&js_code=${code}&grant_type=authorization_code`;

  https.get(url, (apiRes) => {
    let data = '';
    apiRes.on('data', (chunk) => { data += chunk; });
    apiRes.on('end', () => {
      try {
        const result = JSON.parse(data);
        if (result.errcode) {
          return res.status(400).json({ error: '微信登录失败', detail: result.errmsg });
        }
        const { token, user_id } = login(result.openid);
        res.json({ token, user_id });
      } catch (e) {
        res.status(500).json({ error: '解析微信响应失败' });
      }
    });
  }).on('error', () => {
    res.status(500).json({ error: '请求微信服务器失败' });
  });
});

module.exports = router;
