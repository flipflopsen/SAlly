import React, { memo } from 'react'

const OutputConnection = memo(({ data, type }) => {
  const color = '#ef4444'
  const icon = '🔗'

  return (
    <div
      className="connection-template"
      style={{
        backgroundColor: color,
        border: `2px solid ${color}`,
        borderRadius: '4px',
        padding: '8px',
        color: 'white',
        textAlign: 'center',
        minWidth: '80px'
      }}
    >
      <div className="connection-icon">
        {icon}
      </div>
      <div className="connection-label">{data?.label || type}</div>
    </div>
  )
})

OutputConnection.displayName = 'OutputConnection'

export default OutputConnection