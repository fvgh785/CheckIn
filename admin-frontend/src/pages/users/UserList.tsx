import { useEffect, useState } from 'react';
import { Table, Input, Typography, Tag, Space } from 'antd';
import { SearchOutlined, EyeOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { getUserList } from '../../services/admin';
import dayjs from 'dayjs';

const { Title } = Typography;

interface User {
  user_id: string;
  open_id: string;
  created_at: string;
  total_checkins: number;
  is_member: boolean;
}

export default function UserList() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    loadUsers();
  }, [page, keyword]);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const res = await getUserList({ page, page_size: 20, keyword });
      setUsers(res.data.users);
      setTotal(res.data.total);
    } catch {
      // handled
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { title: 'User ID', dataIndex: 'user_id', key: 'user_id', width: 120, ellipsis: true },
    { title: 'Open ID', dataIndex: 'open_id', key: 'open_id', ellipsis: true },
    { title: '注册时间', dataIndex: 'created_at', key: 'created_at', width: 180,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm') },
    { title: '累计打卡', dataIndex: 'total_checkins', key: 'total_checkins', width: 100 },
    {
      title: '会员', dataIndex: 'is_member', key: 'is_member', width: 80,
      render: (v: boolean) => v ? <Tag color="gold">会员</Tag> : <Tag>普通</Tag>,
    },
    {
      title: '操作', key: 'action', width: 80,
      render: (_: unknown, record: User) => (
        <Space>
          <a onClick={() => navigate(`/users/${record.user_id}`)}><EyeOutlined /> 详情</a>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4}>用户管理</Title>
      <Input
        placeholder="搜索 Open ID..."
        prefix={<SearchOutlined />}
        value={keyword}
        onChange={(e) => { setKeyword(e.target.value); setPage(1); }}
        style={{ width: 300, marginBottom: 16 }}
        allowClear
      />
      <Table
        dataSource={users}
        columns={columns}
        rowKey="user_id"
        loading={loading}
        pagination={{
          current: page,
          total,
          pageSize: 20,
          onChange: (p) => setPage(p),
          showTotal: (t) => `共 ${t} 条`,
        }}
      />
    </div>
  );
}
