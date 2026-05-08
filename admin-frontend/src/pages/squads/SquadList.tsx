import { useEffect, useState } from 'react';
import { Table, Typography, Button, Modal, message } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import { getSquadList, deleteSquad } from '../../services/admin';
import dayjs from 'dayjs';

const { Title } = Typography;

interface Squad {
  id: string;
  name: string;
  code: string;
  owner_id: string;
  owner_open_id: string;
  max_members: number;
  member_count: number;
  current_streak: number;
  max_streak: number;
  created_at: string;
}

export default function SquadList() {
  const [data, setData] = useState<Squad[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  useEffect(() => { loadData(); }, [page]);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await getSquadList({ page, page_size: 20 });
      setData(res.data.squads);
      setTotal(res.data.total);
    } catch { /* handled */ } finally { setLoading(false); }
  };

  const handleDelete = (id: string, name: string) => {
    Modal.confirm({
      title: `确认解散小队 "${name}"？`,
      content: '解散后所有成员将被移出',
      onOk: async () => {
        await deleteSquad(id);
        message.success('小队已解散');
        loadData();
      },
    });
  };

  const columns = [
    { title: '小队名称', dataIndex: 'name', key: 'name' },
    { title: '邀请码', dataIndex: 'code', key: 'code', width: 100 },
    { title: '队长', dataIndex: 'owner_open_id', key: 'owner_open_id', width: 140, ellipsis: true },
    { title: '成员', key: 'members', width: 80,
      render: (_: unknown, r: Squad) => `${r.member_count}/${r.max_members}` },
    { title: '当前连胜', dataIndex: 'current_streak', key: 'current_streak', width: 90 },
    { title: '最长连胜', dataIndex: 'max_streak', key: 'max_streak', width: 90 },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 110,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD') },
    {
      title: '操作', key: 'action', width: 80,
      render: (_: unknown, r: Squad) => (
        <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id, r.name)}>解散</Button>
      ),
    },
  ];

  return (
    <div>
      <Title level={4}>小队管理</Title>
      <Table dataSource={data} columns={columns} rowKey="id" loading={loading}
        pagination={{ current: page, total, pageSize: 20, onChange: (p) => setPage(p), showTotal: (t) => `共 ${t} 个小队` }} />
    </div>
  );
}
