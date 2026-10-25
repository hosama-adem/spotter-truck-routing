type StatusBannerProps = {
  tone?: 'info' | 'error' | 'success'
  title?: string
  message: string
  actionLabel?: string
  onAction?: () => void
  actionDisabled?: boolean
}

export function StatusBanner({
  tone = 'info',
  title,
  message,
  actionLabel,
  onAction,
  actionDisabled = false,
}: StatusBannerProps) {
  return (
    <div
      className={`status-banner status-banner-${tone}`}
      role={tone === 'error' ? 'alert' : 'status'}
    >
      <div className="status-banner-copy">
        {title ? <p className="status-banner-title">{title}</p> : null}
        <p className="status-banner-message">{message}</p>
      </div>
      {actionLabel && onAction ? (
        <button
          type="button"
          className="btn-secondary"
          disabled={actionDisabled}
          onClick={onAction}
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  )
}
