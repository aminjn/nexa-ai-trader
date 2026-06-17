interface LogoProps { size?: number }

export default function Logo({ size = 36 }: LogoProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" fill="none">
      <polygon points="18,2 32,10 32,26 18,34 4,26 4,10" fill="none" stroke="var(--accent)" strokeWidth="1.5" />
      <circle cx="18" cy="18" r="5" fill="var(--accent)" opacity="0.9" />
      <line x1="18" y1="13" x2="18" y2="2" stroke="var(--accent)" strokeWidth="1" opacity="0.6" />
      <line x1="22.3" y1="15.5" x2="32" y2="10" stroke="var(--accent)" strokeWidth="1" opacity="0.6" />
      <line x1="22.3" y1="20.5" x2="32" y2="26" stroke="var(--accent)" strokeWidth="1" opacity="0.6" />
      <line x1="18" y1="23" x2="18" y2="34" stroke="var(--accent)" strokeWidth="1" opacity="0.6" />
      <line x1="13.7" y1="20.5" x2="4" y2="26" stroke="var(--accent)" strokeWidth="1" opacity="0.6" />
      <line x1="13.7" y1="15.5" x2="4" y2="10" stroke="var(--accent)" strokeWidth="1" opacity="0.6" />
      <circle cx="18" cy="2" r="2" fill="var(--accent2)" />
      <circle cx="32" cy="10" r="2" fill="var(--accent)" />
      <circle cx="32" cy="26" r="2" fill="var(--accent)" />
    </svg>
  )
}
