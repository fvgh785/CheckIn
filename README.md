# 每日打卡小程序

简洁的打卡小程序，支持微信登录、连续打卡统计和成就展示。

## 功能

- 微信一键登录
- 每日一键打卡
- 连续打卡天数
- 最高连续记录
- 累计打卡天数
- 仅查看自己的打卡信息

## 技术栈

**后端**: Node.js + Express + SQLite  
**前端**: 微信小程序原生  
**部署**: Docker Compose

## 快速部署

### 1. 配置微信小程序凭证

在微信公众平台获取 AppID 和 AppSecret，编辑 `docker-compose.yml`：

```yaml
environment:
  - WX_APP_ID=你的小程序AppID
  - WX_APP_SECRET=你的小程序AppSecret
```

### 2. 部署后端到阿里云

```bash
cd CheckIn
docker-compose up -d
```

### 3. 配置域名

- 在阿里云购买域名并完成备案
- 配置 Nginx 反向代理到 `localhost:3000`
- 启用 HTTPS（微信小程序要求）

Nginx 配置示例：

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /api/ {
        proxy_pass http://127.0.0.1:3000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 4. 配置小程序

编辑 `miniprogram/app.js`，修改 `apiBase` 为你的后端地址：

```javascript
globalData: {
  apiBase: 'https://your-domain.com/api',
  token: ''
}
```

### 5. 微信小程序后台配置

1. 登录微信公众平台 (https://mp.weixin.qq.com/)
2. 开发管理 -> 开发设置 -> 服务器域名
3. 添加 request 合法域名：`https://your-domain.com`
4. 上传小程序代码并提交审核

## 项目结构

```
CheckIn/
├── backend/
│   ├── src/
│   │   ├── index.js              # 服务入口
│   │   ├── db.js                 # 数据库操作 + 会话管理
│   │   ├── middleware/
│   │   │   └── auth.js           # Token 认证中间件
│   │   └── routes/
│   │       ├── auth.js           # 微信登录接口
│   │       └── checkin.js        # 打卡 API 路由
│   ├── Dockerfile
│   └── package.json
├── miniprogram/
│   ├── app.js                    # 小程序入口 + 登录态检查
│   ├── app.json                  # 小程序配置
│   ├── app.wxss                  # 全局样式
│   ├── pages/
│   │   ├── login/                # 微信登录页
│   │   └── index/                # 打卡主页
│   └── sitemap.json
├── docker-compose.yml            # Docker 编排
└── .gitignore
```

## API 接口

### POST /api/auth/login

微信登录

```json
// Request
{ "code": "wx_login_code" }

// Response
{ "token": "xxx", "user_id": 1 }
```

### POST /api/checkin

打卡 (需要 Bearer Token)

```json
// Headers
Authorization: Bearer {token}

// Response
{ "success": true, "message": "打卡成功" }
```

### GET /api/stats

查询统计 (需要 Bearer Token)

```json
// Headers
Authorization: Bearer {token}

// Response
{
  "has_checked_today": true,
  "current_streak": 5,
  "max_streak": 12,
  "total_days": 30
}
```

## 安全说明

- 所有打卡和统计接口均需携带有效 Token
- Token 有效期 7 天，过期需重新登录
- 用户只能查看和操作自己的打卡数据
- 微信登录凭证通过微信官方 API 验证

## 生产环境建议

1. **数据备份**: 定期备份 `data/checkin.db` 文件
2. **安全加固**: 添加请求频率限制
3. **监控日志**: 配置日志收集和监控告警
4. **Token 存储**: 生产环境建议使用 Redis 存储会话
