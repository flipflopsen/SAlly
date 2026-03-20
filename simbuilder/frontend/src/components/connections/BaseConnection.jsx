import React, { memo } from 'react'

const BaseConnection = memo(({ data, type }) => {
  const getConnectionColor = (connectionType) => {
    switch (connectionType) {
      case 'input':
        return '#46A832' // Copper color
      case 'output':
        return '#A83232' // Blue for data
      case 'monitor':
        return '#4A90E2' // Blue for data
      default:
        return '#666'
    }
  }

  const getConnectionIcon = (connectionType) => {
    switch (connectionType) {
      case 'copper_cable':
        return '⚡'
      case 'data_cable':
        return '📡'
      default:
        return '🔗'
    }
  }

  return (
    <div
      className="connection-template"
      style={{
        backgroundColor: getConnectionColor(type),
        border: `2px solid ${getConnectionColor(type)}`,
        borderRadius: '4px',
        padding: '8px',
        color: 'white',
        textAlign: 'center',
        minWidth: '80px'
      }}
    >
      <div className="connection-icon">
        {getConnectionIcon(type)}
      </div>
      <div className="connection-label">{data?.label || type}</div>
    </div>
  )
})

BaseConnection.displayName = 'BaseConnection'

export default BaseConnection