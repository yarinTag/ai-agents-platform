import React from 'react';
import { tokens } from '../theme/tokens';

export interface SurfaceCardProps {
  children: React.ReactNode;
  variant?: 'default' | 'primary' | 'raised';
  padding?: string;
  style?: React.CSSProperties;
  className?: string;
}

export const SurfaceCard: React.FC<SurfaceCardProps> = ({
  children,
  variant = 'default',
  padding = tokens.spacing.lg,
  style,
  className,
}) => {
  const bgMap = {
    default: tokens.colors.bg.card,
    primary: tokens.colors.bg.primary,
    raised: tokens.colors.bg.surface,
  };

  return (
    <div
      className={className}
      style={{
        background: bgMap[variant],
        border: `1px solid ${tokens.colors.border.default}`,
        borderRadius: tokens.radii.md,
        padding,
        color: tokens.colors.text.primary,
        boxShadow: tokens.shadows.card,
        ...style,
      }}
    >
      {children}
    </div>
  );
};
