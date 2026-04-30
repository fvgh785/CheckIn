const { verifyToken } = require('../db');

function authMiddleware(req, res, next) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: '未登录' });
  }

  const token = authHeader.split(' ')[1];
  const session = verifyToken(token);
  
  if (!session) {
    return res.status(401).json({ error: '登录已过期' });
  }

  req.user = session;
  next();
}

module.exports = authMiddleware;
