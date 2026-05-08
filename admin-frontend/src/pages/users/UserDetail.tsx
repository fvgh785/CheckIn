import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Descriptions, Tag, Table, Typography, Button, Spin } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { getUserDetail } from '../../services/admin';
import dayjs from 'dayjs';

const { Title } = Typography;

interface UserDetailData {
  user_id: string;
  open_id: string;
  phone: string;
  nickname: string;
  email: string;
  created_at: string;
  stats: {
    has_checked_today: boolean;
    current_streak: number;
    max_streak: number;
    total_days: number;
  };
  membership: {
    active: boolean;
    level: string | null;
    start_date: string | null;
    end_date: string | null;
  };
  recent_checkins: string[];
}

export default function UserDetail() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const [user, setUser] = useState<UserDetailData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (userId) loadUser();
  }, [userId]);

  const loadUser = async () => {
    try {
      const res = await getUserDetail(userId!);
      setUser(res.data);
    } catch {
      // handled
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!user) return <div>用户不存在</div>;

  const checkinColumns = [
    { title: '序号', key: 'index', width: 60, render: (_: unknown, __: unknown, i: number) => i + 1 },
    { title: '打卡日期', dataIndex: 'date', key: 'date' },
  ];

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/users')} style={{ marginBottom: 16 }}>
        返回列表
      </Button>
      <Title level={4}>用户详情</Title>

      <Card title="基本信息" style={{ marginBottom: 16 }}>
        <Descriptions column={2}>
          <Descriptions.Item label="User ID">{user.user_id}</Descriptions.Item>
          <Descriptions.Item label="Open ID">{user.open_id}</Descriptions.Item>
          <Descriptions.Item label="手机号">{user.phone || '-'}</Descriptions.Item>
          <Descriptions.Item label="邮箱">{user.email || '-'}</Descriptions.Item>
          <Descriptions.Item label="昵称">{user.nickname || '-'}</Descriptions.Item>
          <Descriptions.Item label="注册时间">{dayjs(user.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
          <Descriptions.Item label="今日打卡">
            {user.stats.has_checked_today ? <Tag color="green">已打卡</Tag> : <Tag color="red">未打卡</Tag>}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="打卡统计" style={{ marginBottom: 16 }}>
        <Descriptions column={3}>
          <Descriptions.Item label="累计打卡">{user.stats.total_days} 天</Descriptions.Item>
          <Descriptions.Item label="当前连续">{user.stats.current_streak} 天</Descriptions.Item>
          <Descriptions.Item label="最长连续">{user.stats.max_streak} 天</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="会员状态" style={{ marginBottom: 16 }}>
        <Descriptions column={2}>
          <Descriptions.Item label="是否会员">
            {user.membership.active ? <Tag color="gold">是</Tag> : <Tag>否</Tag>}
          </Descriptions.Item>
          <Descriptions.Item label="会员等级">{user.membership.level || '-'}</Descriptions.Item>
          <Descriptions.Item label="开始日期">{user.membership.start_date || '-'}</Descriptions.Item>
          <Descriptions.Item label="到期日期">{user.membership.end_date || '-'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="近30天打卡记录">
        <Table
          dataSource={user.recent_checkins.map((d) => ({ date: d }))}
          columns={checkinColumns}
          rowKey="date"
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  );
}
