import React, { memo } from 'react'

const InputConnection = memo(({ data, type }) => {
  return (
    <div
      className="connection-template"
      style={{
        backgroundColor: '#22c55e',
        border: `2px solid #22c55e`,
        borderRadius: '4px',
        padding: '8px',
        color: 'white',
        textAlign: 'center',
        minWidth: '80px'
      }}
    >
      <div className="connection-icon">
        ⬅️
      </div>
      <div className="connection-label">{data?.label || 'Input'}</div>
    </div>
  )
})

InputConnection.displayName = 'InputConnection'

export default InputConnection