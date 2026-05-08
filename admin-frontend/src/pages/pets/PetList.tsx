import { useEffect, useState } from 'react';
import { Table, Typography, Button, Modal, InputNumber, Select, message } from 'antd';
import { EditOutlined } from '@ant-design/icons';
import { getPetList, updatePet } from '../../services/admin';
import dayjs from 'dayjs';

const { Title } = Typography;

interface Pet { id: string; user_id: string; open_id: string; pet_type: string; pet_name: string; stage: number; mood: number; hunger: number; exp: number; last_feed_date: string | null; created_at: string; }

const STAGE_NAMES: Record<number, string> = { 1: '蛋', 2: '幼崽', 3: '成年', 4: '传说' };
const PET_TYPES = ['cat', 'dog', 'bunny', 'panda'];

export default function PetList() {
  const [data, setData] = useState<Pet[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingPet, setEditingPet] = useState<Pet | null>(null);
  const [editValues, setEditValues] = useState<Record<string, number | string>>({});

  useEffect(() => { loadData(); }, [page]);

  const loadData = async () => {
    setLoading(true);
    try { const res = await getPetList({ page, page_size: 20 }); setData(res.data.pets); setTotal(res.data.total); }
    catch { /* handled */ } finally { setLoading(false); }
  };

  const openEdit = (pet: Pet) => {
    setEditingPet(pet);
    setEditValues({ pet_name: pet.pet_name, pet_type: pet.pet_type, stage: pet.stage, mood: pet.mood, hunger: pet.hunger, exp: pet.exp });
    setEditModalOpen(true);
  };

  const handleEdit = async () => {
    if (!editingPet) return;
    try { await updatePet(editingPet.id, editValues); message.success('更新成功'); setEditModalOpen(false); loadData(); }
    catch { /* handled */ }
  };

  const columns = [
    { title: '宠物名', dataIndex: 'pet_name', key: 'pet_name', width: 100 },
    { title: 'User ID', dataIndex: 'user_id', key: 'user_id', width: 120, ellipsis: true },
    { title: '种类', dataIndex: 'pet_type', key: 'pet_type', width: 70 },
    { title: '阶段', dataIndex: 'stage', key: 'stage', width: 70, render: (v: number) => STAGE_NAMES[v] || v },
    { title: '心情', dataIndex: 'mood', key: 'mood', width: 60 },
    { title: '饥饿', dataIndex: 'hunger', key: 'hunger', width: 60 },
    { title: '经验', dataIndex: 'exp', key: 'exp', width: 60 },
    { title: '最后喂食', dataIndex: 'last_feed_date', key: 'last_feed_date', width: 110, render: (v: string | null) => v || '-' },
    { title: '操作', key: 'action', width: 80, render: (_: unknown, r: Pet) => <Button type="link" icon={<EditOutlined />} onClick={() => openEdit(r)}>编辑</Button> },
  ];

  return (
    <div>
      <Title level={4}>宠物管理</Title>
      <Table dataSource={data} columns={columns} rowKey="id" loading={loading}
        pagination={{ current: page, total, pageSize: 20, onChange: (p) => setPage(p), showTotal: (t) => `共 ${t} 只` }} />

      <Modal title="编辑宠物" open={editModalOpen} onOk={handleEdit}
        onCancel={() => setEditModalOpen(false)} okText="确认" cancelText="取消">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 16 }}>
          <div>宠物名: <InputNumber value={editValues.pet_name as string} onChange={(v) => setEditValues({ ...editValues, pet_name: v || '' })} /></div>
          <div>种类: <Select value={editValues.pet_type as string} onChange={(v) => setEditValues({ ...editValues, pet_type: v })} options={PET_TYPES.map(t => ({ label: t, value: t }))} style={{ width: 120 }} /></div>
          <div>阶段: <InputNumber min={1} max={4} value={editValues.stage as number} onChange={(v) => setEditValues({ ...editValues, stage: v || 1 })} /></div>
          <div>心情: <InputNumber min={0} max={100} value={editValues.mood as number} onChange={(v) => setEditValues({ ...editValues, mood: v || 0 })} /></div>
          <div>饥饿: <InputNumber min={0} max={100} value={editValues.hunger as number} onChange={(v) => setEditValues({ ...editValues, hunger: v || 0 })} /></div>
          <div>经验: <InputNumber min={0} value={editValues.exp as number} onChange={(v) => setEditValues({ ...editValues, exp: v || 0 })} /></div>
        </div>
      </Modal>
    </div>
  );
}
