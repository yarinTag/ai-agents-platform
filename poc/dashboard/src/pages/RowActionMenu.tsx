import { Button, Dropdown } from 'antd';
import type { MenuProps } from 'antd';
import { EllipsisOutlined } from '@ant-design/icons';

export function RowActionMenu({ label, items }: { label: string; items: MenuProps['items'] }) {
  return (
    <Dropdown menu={{ items }} trigger={['click']}>
      <Button size="small" icon={<EllipsisOutlined />} aria-label={label} title={label} />
    </Dropdown>
  );
}
