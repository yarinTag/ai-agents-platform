/**
 * Centralized UI Design Tokens.
 * Maps 1:1 to :root CSS custom properties defined in index.css.
 * All UI components MUST import and use these tokens instead of hardcoded hex strings.
 */

export const tokens = {
  colors: {
    bg: {
      canvas: 'var(--bg-canvas)',
      primary: 'var(--bg-primary)',
      secondary: 'var(--bg-secondary)',
      card: 'var(--bg-card)',
      cardHover: 'var(--bg-card-hover)',
      surface: 'var(--bg-surface)',
      surfaceRaised: 'var(--bg-surface-raised)',
      sidebar: 'var(--bg-sidebar)',
    },
    border: {
      subtle: 'var(--border-subtle)',
      default: 'var(--border-default)',
      hover: 'var(--border-hover)',
      focus: 'var(--border-focus)',
    },
    text: {
      primary: 'var(--text-primary)',
      secondary: 'var(--text-secondary)',
      muted: 'var(--text-muted)',
      accent: 'var(--text-accent)',
      inverse: 'var(--text-inverse)',
    },
    status: {
      success: 'var(--status-success)',
      successBg: 'var(--status-success-bg)',
      successBorder: 'var(--status-success-border)',
      warning: 'var(--status-warning)',
      warningBg: 'var(--status-warning-bg)',
      warningBorder: 'var(--status-warning-border)',
      error: 'var(--status-error)',
      errorBg: 'var(--status-error-bg)',
      errorBorder: 'var(--status-error-border)',
      info: 'var(--status-info)',
      infoBg: 'var(--status-info-bg)',
      infoBorder: 'var(--status-info-border)',
    },
    accent: {
      primary: 'var(--accent-primary)',
      primaryHover: 'var(--accent-primary-hover)',
      secondary: 'var(--accent-secondary)',
      blue: 'var(--accent-blue)',
      green: 'var(--accent-green)',
      amber: 'var(--accent-amber)',
      purple: 'var(--accent-purple)',
    },
  },
  spacing: {
    xxs: 'var(--space-2xs)',
    xs: 'var(--space-xs)',
    sm: 'var(--space-sm)',
    md: 'var(--space-md)',
    lg: 'var(--space-lg)',
    xl: 'var(--space-xl)',
    xxl: 'var(--space-2xl)',
    xxxl: 'var(--space-3xl)',
  },
  radii: {
    sm: 'var(--radius-sm)',
    md: 'var(--radius-md)',
    lg: 'var(--radius-lg)',
    xl: 'var(--radius-xl)',
    full: 'var(--radius-full)',
  },
  typography: {
    fontSans: 'var(--font-sans)',
    fontMono: 'var(--font-mono)',
    size: {
      xs: 'var(--font-size-xs)',
      sm: 'var(--font-size-sm)',
      md: 'var(--font-size-md)',
      lg: 'var(--font-size-lg)',
      xl: 'var(--font-size-xl)',
      xxl: 'var(--font-size-2xl)',
    },
    weight: {
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
      heavy: 800,
    },
  },
  shadows: {
    sm: 'var(--shadow-sm)',
    md: 'var(--shadow-md)',
    lg: 'var(--shadow-lg)',
    card: 'var(--shadow-card)',
  },
} as const;

export const modalTokenStyles = {
  body: {
    background: tokens.colors.bg.card,
    color: tokens.colors.text.primary,
  },
  header: {
    background: tokens.colors.bg.card,
    borderBottom: `1px solid ${tokens.colors.border.subtle}`,
    color: tokens.colors.text.primary,
  },
} as const;

export const inputTokenStyle = {
  background: tokens.colors.bg.primary,
  borderColor: tokens.colors.border.default,
  color: tokens.colors.text.primary,
} as const;

export type DesignTokens = typeof tokens;
