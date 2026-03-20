import React, { memo } from 'react'

const MonitorConnection = memo(({ data, type }) => {
  return (
    <div
      className="connection-template"
      style={{
        backgroundColor: '#3b82f6',
        border: '2px solid #3b82f6',
        borderRadius: '4px',
        padding: '8px',
        color: 'white',
        textAlign: 'center',
        minWidth: '80px'
      }}
    >
      <div className="connection-icon">
        📊
      </div>
      <div className="connection-label">{data?.label || type}</div>
    </div>
  )
})

MonitorConnection.displayName = 'MonitorConnection'

export default MonitorConnection