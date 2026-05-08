import { useEffect, useState } from 'react';
import { Card, Descriptions, Typography, InputNumber, Button, message, Spin } from 'antd';
import { getConfig, updateConfig } from '../../services/admin';

const { Title } = Typography;

interface Config { makeup_card_limit: number; membership_level: string; app_version: string; }

export default function SystemConfig() {
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [makeupLimit, setMakeupLimit] = useState(3);

  useEffect(() => { loadConfig(); }, []);

  const loadConfig = async () => {
    try { const res = await getConfig(); setConfig(res.data); setMakeupLimit(res.data.makeup_card_limit); }
    catch { /* handled */ } finally { setLoading(false); }
  };

  const handleSave = async () => {
    try { await updateConfig({ makeup_card_limit: makeupLimit }); message.success('配置已保存（部分配置需重启生效）'); }
    catch { /* handled */ }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  return (
    <div>
      <Title level={4}>系统配置</Title>
      <Card title="基本配置" style={{ maxWidth: 600, marginBottom: 16 }}>
        <Descriptions column={1}>
          <Descriptions.Item label="应用版本">{config?.app_version || '-'}</Descriptions.Item>
          <Descriptions.Item label="会员等级">{config?.membership_level || '-'}</Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title="业务参数" style={{ maxWidth: 600 }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 16 }}>
          <span>补签卡月限额:</span>
          <InputNumber min={0} max={10} value={makeupLimit} onChange={(v) => setMakeupLimit(v || 0)} />
        </div>
        <Button type="primary" onClick={handleSave}>保存配置</Button>
      </Card>
    </div>
  );
}
