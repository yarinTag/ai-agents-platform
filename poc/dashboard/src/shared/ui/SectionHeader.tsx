import React from 'react';
import { tokens } from '../theme/tokens';

export interface SectionHeaderProps {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  style?: React.CSSProperties;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  title,
  subtitle,
  icon,
  actions,
  style,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: tokens.spacing.md,
        ...style,
      }}
    >
      <div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing.sm,
            color: tokens.colors.text.primary,
            fontSize: tokens.typography.size.lg,
            fontWeight: tokens.typography.weight.bold,
          }}
        >
          {icon}
          <span>{title}</span>
        </div>
        {subtitle && (
          <div
            style={{
              color: tokens.colors.text.secondary,
              fontSize: tokens.typography.size.sm,
              marginTop: tokens.spacing.xxs,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
      {actions && <div style={{ display: 'flex', gap: tokens.spacing.sm }}>{actions}</div>}
    </div>
  );
};
