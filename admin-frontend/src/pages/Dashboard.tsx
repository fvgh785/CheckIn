import { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Table, Typography, Spin } from 'antd';
import {
  UserOutlined,
  CheckCircleOutlined,
  CrownOutlined,
  FireOutlined,
} from '@ant-design/icons';
import { getDashboard } from '../../services/admin';
import dayjs from 'dayjs';

const { Title } = Typography;

interface Stats {
  total_users: number;
  today_checkins: number;
  active_members: number;
  total_checkins: number;
  total_squads: number;
  checkin_trend: { date: string; count: number }[];
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const res = await getDashboard();
      setStats(res.data);
    } catch {
      // handled by interceptor
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  const trendColumns = [
    { title: '日期', dataIndex: 'date', key: 'date' },
    { title: '打卡人数', dataIndex: 'count', key: 'count' },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>数据看板</Title>
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic title="用户总数" value={stats?.total_users || 0} prefix={<UserOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic title="今日打卡" value={stats?.today_checkins || 0} prefix={<CheckCircleOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic title="活跃会员" value={stats?.active_members || 0} prefix={<CrownOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic title="总打卡次数" value={stats?.total_checkins || 0} prefix={<FireOutlined />} />
          </Card>
        </Col>
      </Row>
      <Card title="近7天打卡趋势" style={{ marginTop: 24 }}>
        <Table
          dataSource={stats?.checkin_trend || []}
          columns={trendColumns}
          rowKey="date"
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  );
}
