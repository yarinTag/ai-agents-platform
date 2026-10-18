import React from 'react';
import { tokens } from '../theme/tokens';

export type StatusTone = 'success' | 'warning' | 'error' | 'info' | 'neutral';

export interface StatusBadgeProps {
  tone?: StatusTone;
  label: React.ReactNode;
  icon?: React.ReactNode;
  style?: React.CSSProperties;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  tone = 'neutral',
  label,
  icon,
  style,
}) => {
  const toneStyles: Record<StatusTone, { bg: string; border: string; color: string }> = {
    success: {
      bg: tokens.colors.status.successBg,
      border: tokens.colors.status.successBorder,
      color: tokens.colors.status.success,
    },
    warning: {
      bg: tokens.colors.status.warningBg,
      border: tokens.colors.status.warningBorder,
      color: tokens.colors.status.warning,
    },
    error: {
      bg: tokens.colors.status.errorBg,
      border: tokens.colors.status.errorBorder,
      color: tokens.colors.status.error,
    },
    info: {
      bg: tokens.colors.status.infoBg,
      border: tokens.colors.status.infoBorder,
      color: tokens.colors.status.info,
    },
    neutral: {
      bg: tokens.colors.bg.primary,
      border: tokens.colors.border.default,
      color: tokens.colors.text.secondary,
    },
  };

  const current = toneStyles[tone];

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: tokens.spacing.xs,
        padding: `${tokens.spacing.xxs} ${tokens.spacing.sm}`,
        borderRadius: tokens.radii.sm,
        fontSize: tokens.typography.size.xs,
        fontWeight: tokens.typography.weight.semibold,
        background: current.bg,
        border: `1px solid ${current.border}`,
        color: current.color,
        ...style,
      }}
    >
      {icon}
      {label}
    </span>
  );
};
