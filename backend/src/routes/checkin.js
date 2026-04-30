const express = require('express');
const router = express.Router();
const authMiddleware = require('../middleware/auth');
const { checkInByUserId, getStatsByUserId } = require('../db');

router.post('/checkin', authMiddleware, (req, res) => {
  const result = checkInByUserId(req.user.userId);
  if (result.success) {
    return res.json(result);
  }
  return res.status(409).json(result);
});

router.get('/stats', authMiddleware, (req, res) => {
  const stats = getStatsByUserId(req.user.userId);
  return res.json(stats);
});

module.exports = router;
