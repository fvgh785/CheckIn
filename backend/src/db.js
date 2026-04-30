const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const dbPath = path.join(__dirname, '..', 'data', 'checkin.json');
const dataDir = path.dirname(dbPath);

if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

let data = { users: [], checkIns: [] };

if (fs.existsSync(dbPath)) {
  try {
    data = JSON.parse(fs.readFileSync(dbPath, 'utf8'));
  } catch (e) {
    data = { users: [], checkIns: [] };
  }
}

function save() {
  fs.writeFileSync(dbPath, JSON.stringify(data, null, 2));
}

function getOrCreateUser(openId) {
  let user = data.users.find(u => u.open_id === openId);
  if (!user) {
    user = { id: crypto.randomUUID(), open_id: openId, created_at: new Date().toISOString() };
    data.users.push(user);
    save();
  }
  return user;
}

function generateToken() {
  return crypto.randomBytes(32).toString('hex');
}

const sessions = new Map();

function login(openId) {
  const user = getOrCreateUser(openId);
  const token = generateToken();
  sessions.set(token, { userId: user.id, openId: user.open_id, createdAt: Date.now() });
  return { token, user_id: user.id };
}

function verifyToken(token) {
  const session = sessions.get(token);
  if (!session) return null;
  if (Date.now() - session.createdAt > 7 * 24 * 60 * 60 * 1000) {
    sessions.delete(token);
    return null;
  }
  return session;
}

function logout(token) {
  sessions.delete(token);
}

function checkInByUserId(userId) {
  const user = data.users.find(u => u.id === userId);
  if (!user) return { success: false, message: '用户不存在' };

  const today = new Date().toISOString().split('T')[0];
  const exists = data.checkIns.some(c => c.user_id === userId && c.check_date === today);
  
  if (exists) {
    return { success: false, message: '今日已打卡' };
  }

  data.checkIns.push({
    id: crypto.randomUUID(),
    user_id: userId,
    check_date: today,
    created_at: new Date().toISOString()
  });
  save();
  return { success: true, message: '打卡成功' };
}

function getStatsByUserId(userId) {
  const allCheckIns = data.checkIns.filter(c => c.user_id === userId).sort((a, b) => a.check_date.localeCompare(b.check_date));
  const today = new Date().toISOString().split('T')[0];
  const hasCheckedToday = allCheckIns.some(c => c.check_date === today);

  let currentStreak = 0;
  let maxStreak = 0;
  let tempStreak = 0;
  let prevDate = null;

  for (const record of allCheckIns) {
    const currDate = new Date(record.check_date);
    if (prevDate) {
      const diffDays = Math.floor((currDate - prevDate) / (1000 * 60 * 60 * 24));
      tempStreak = diffDays === 1 ? tempStreak + 1 : 1;
    } else {
      tempStreak = 1;
    }
    maxStreak = Math.max(maxStreak, tempStreak);
    prevDate = currDate;
  }

  const lastCheckIn = allCheckIns.length > 0 ? allCheckIns[allCheckIns.length - 1] : null;
  if (lastCheckIn) {
    const lastDate = new Date(lastCheckIn.check_date);
    const todayDate = new Date(today);
    const diffDays = Math.floor((todayDate - lastDate) / (1000 * 60 * 60 * 24));
    
    if (diffDays <= 1) {
      let streak = 0;
      let checkDate = new Date(lastCheckIn.check_date);
      while (true) {
        const dateStr = checkDate.toISOString().split('T')[0];
        const exists = allCheckIns.some(c => c.check_date === dateStr);
        if (exists) {
          streak++;
          checkDate.setDate(checkDate.getDate() - 1);
        } else {
          break;
        }
      }
      currentStreak = streak;
    }
  }

  return {
    has_checked_today: hasCheckedToday,
    current_streak: currentStreak,
    max_streak: maxStreak,
    total_days: allCheckIns.length
  };
}

module.exports = { getOrCreateUser, login, verifyToken, logout, checkInByUserId, getStatsByUserId };
