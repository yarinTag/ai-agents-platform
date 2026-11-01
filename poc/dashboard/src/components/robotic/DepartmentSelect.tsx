import React from 'react';
import { Select, Tag, Space, Typography } from 'antd';
import { BankOutlined } from '@ant-design/icons';
import { useAuth } from '../../context/AuthContext';
import { Department } from '../../types/auth';

const { Text } = Typography;

export interface DepartmentSelectProps {
  value?: string | null;
  onChange?: (departmentId: string, department?: Department) => void;
  placeholder?: string;
  disabled?: boolean;
  style?: React.CSSProperties;
  className?: string;
  size?: 'large' | 'middle' | 'small';
  showBudgetBadge?: boolean;
  allowClear?: boolean;
}

export const DepartmentSelect: React.FC<DepartmentSelectProps> = ({
  value,
  onChange,
  placeholder = 'Select Department...',
  disabled = false,
  style,
  className,
  size = 'middle',
  showBudgetBadge = true,
  allowClear = false,
}) => {
  const { departments } = useAuth();

  const handleChange = (selectedId: string) => {
    if (onChange) {
      const foundDept = departments.find((d) => (d.id || d.department_id) === selectedId);
      onChange(selectedId, foundDept);
    }
  };

  return (
    <Select
      value={value || undefined}
      onChange={handleChange}
      placeholder={placeholder}
      disabled={disabled}
      size={size}
      allowClear={allowClear}
      className={className}
      style={{ minWidth: 240, width: '100%', ...style }}
      dropdownStyle={{ background: '#161b22', borderColor: '#30363d' }}
      showSearch
      filterOption={(input, option) => {
        const text = String(option?.['data-name'] || '').toLowerCase();
        return text.includes(input.toLowerCase());
      }}
      optionLabelProp="label"
    >
      {departments.map((dept) => {
        const deptId = dept.id || dept.department_id || '';
        const spend = Number(dept.current_spend_usd || 0);
        const budget = Number(dept.monthly_budget_usd || 0);
        const pct = budget > 0 ? Math.round((spend / budget) * 100) : 0;
        const isNearLimit = pct >= 85;
        const isOverLimit = pct >= 100;

        const tagColor = isOverLimit ? 'error' : isNearLimit ? 'warning' : 'success';

        return (
          <Select.Option
            key={deptId}
            value={deptId}
            data-name={dept.name}
            label={
              <Space size={6}>
                <BankOutlined style={{ color: '#10b981' }} />
                <span>{dept.name}</span>
                {showBudgetBadge && (
                  <Tag bordered={false} color={tagColor} style={{ fontSize: 10, margin: 0, padding: '0 5px' }}>
                    ${spend.toFixed(0)} / ${budget.toFixed(0)}
                  </Tag>
                )}
              </Space>
            }
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '2px 0' }}>
              <div>
                <div style={{ fontWeight: 600, color: '#f0f6fc', fontSize: 13 }}>{dept.name}</div>
                {dept.description && (
                  <div style={{ fontSize: 11, color: '#8b949e', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {dept.description}
                  </div>
                )}
              </div>
              {showBudgetBadge && (
                <div style={{ textAlign: 'right', marginLeft: 8 }}>
                  <Tag bordered={false} color={tagColor} style={{ fontSize: 11, margin: 0 }}>
                    ${spend.toFixed(0)} / ${budget.toFixed(0)} ({pct}%)
                  </Tag>
                </div>
              )}
            </div>
          </Select.Option>
        );
      })}
    </Select>
  );
};

export default DepartmentSelect;
