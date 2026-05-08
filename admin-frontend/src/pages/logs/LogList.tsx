import { useEffect, useState } from 'react';
import { Table, Typography, Select, Space } from 'antd';
import { getLogList } from '../../services/admin';
import dayjs from 'dayjs';

const { Title } = Typography;

interface Log { id: string; admin_id: string; admin_username: string; action: string; target_type: string; target_id: string; detail: string; created_at: string; }

const ACTIONS = ['login', 'logout', 'create', 'update', 'delete'];
const TARGET_TYPES = ['admin', 'user', 'membership', 'checkin', 'squad', 'wish', 'capsule', 'pet', 'config'];

export default function LogList() {
  const [data, setData] = useState<Log[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterAction, setFilterAction] = useState<string | undefined>();
  const [filterTarget, setFilterTarget] = useState<string | undefined>();

  useEffect(() => { loadData(); }, [page, filterAction, filterTarget]);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await getLogList({ page, page_size: 50, action: filterAction, target_type: filterTarget });
      setData(res.data.logs); setTotal(res.data.total);
    } catch { /* handled */ } finally { setLoading(false); }
  };

  const columns = [
    { title: '操作人', dataIndex: 'admin_username', key: 'admin_username', width: 100 },
    { title: '操作', dataIndex: 'action', key: 'action', width: 80 },
    { title: '目标类型', dataIndex: 'target_type', key: 'target_type', width: 100 },
    { title: '目标ID', dataIndex: 'target_id', key: 'target_id', width: 120, ellipsis: true },
    { title: '详情', dataIndex: 'detail', key: 'detail', ellipsis: true },
    { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 170, render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss') },
  ];

  return (
    <div>
      <Title level={4}>操作日志</Title>
      <Space style={{ marginBottom: 16 }}>
        <Select placeholder="筛选操作" allowClear style={{ width: 120 }}
          value={filterAction} onChange={(v) => { setFilterAction(v); setPage(1); }}
          options={ACTIONS.map(a => ({ label: a, value: a }))} />
        <Select placeholder="筛选目标类型" allowClear style={{ width: 140 }}
          value={filterTarget} onChange={(v) => { setFilterTarget(v); setPage(1); }}
          options={TARGET_TYPES.map(t => ({ label: t, value: t }))} />
      </Space>
      <Table dataSource={data} columns={columns} rowKey="id" loading={loading}
        scroll={{ x: 'max-content' }}
        pagination={{ current: page, total, pageSize: 50, onChange: (p) => setPage(p), showTotal: (t) => `共 ${t} 条` }} />
    </div>
  );
}
