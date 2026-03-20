import React from 'react'

const Sidebar = ({ nodeTypes, connectionTypes, selectedConnectionType, onConnectionTypeSelect }) => {
  // Show loading state if data is not available
  if (!nodeTypes || Object.keys(nodeTypes).length === 0) {
    return (
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>Component Library</h2>
        </div>
        <div className="sidebar-content">
          <div className="loading-message">Loading node types...</div>
        </div>
      </aside>
    )
  }

  if (!connectionTypes || Object.keys(connectionTypes).length === 0) {
    return (
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>Component Library</h2>
        </div>
        <div className="sidebar-content">
          <div className="loading-message">Loading connection types...</div>
        </div>
      </aside>
    )
  }

  const onDragStart = (event, itemType, isConnection = false) => {
    event.dataTransfer.setData('application/reactflow', itemType)
    event.dataTransfer.setData('application/reactflow/isConnection', isConnection.toString())
    event.dataTransfer.effectAllowed = 'move'
  }

  // Group nodes by category
  const categorizedNodes = Object.entries(nodeTypes).reduce((acc, [type, meta]) => {
    const category = meta.category || 'Other'
    if (!acc[category]) acc[category] = []
    acc[category].push({ type, ...meta, isConnection: false })
    return acc
  }, {})

  // Group connections by category - Updated for new connection types
  const categorizedConnections = Object.entries(connectionTypes).reduce((acc, [type, meta]) => {
    const category = 'Connections'
    if (!acc[category]) acc[category] = []
    if (type !== 'none') {
      acc[category].push({
        type,
        label: type.charAt(0).toUpperCase() + type.slice(1),
        description: `${type} connection type`,
        isConnection: true
      })
    }
    return acc
  }, {})

  // Combine all items, but prioritize "Nodes" and "Connections" categories
  const allCategories = {
    'Nodes': Object.values(categorizedNodes).flat(),
    'Connections': Object.values(categorizedConnections).flat(),
  }

  // Add any other categories that aren't "Nodes" or "Connections"
  Object.entries(categorizedNodes).forEach(([category, nodes]) => {
    if (category !== 'Nodes' && category !== 'Connections') {
      allCategories[category] = [...(allCategories[category] || []), ...nodes]
    }
  })

  Object.entries(categorizedConnections).forEach(([category, connections]) => {
    if (category !== 'Nodes' && category !== 'Connections') {
      allCategories[category] = [...(allCategories[category] || []), ...connections]
    }
  })

  return (
    <aside className="sidebar">
       <div className="sidebar-header">
         <h2>Component Library</h2>
       </div>
       <div className="sidebar-content">
         {Object.entries(allCategories).map(([category, items]) => (
           <div key={category} className="node-category">
             <h3>{category}{category === 'Connections' && selectedConnectionType === 'none' ? ' (None selected)' : ''}</h3>
             <div className="node-list">
               {items.map((item) => (
                 <div
                   key={item.type}
                   className={`node-item ${item.isConnection ? 'connection-item' : ''} ${item.isConnection && item.type === selectedConnectionType ? 'selected' : ''}`}
                   data-type={item.isConnection ? item.type : undefined}
                   data-selected={item.isConnection && item.type === selectedConnectionType ? 'true' : 'false'}
                   draggable
                   onDragStart={(e) => onDragStart(e, item.type, item.isConnection)}
                   onClick={item.isConnection ? (e) => onConnectionTypeSelect(item.type) : undefined}
                 >
                   <div className="node-item-icon">
                     {item.type.charAt(0).toUpperCase()}
                   </div>
                   <div className="node-item-content">
                     <div className="node-item-label">{item.label}</div>
                     <div className="node-item-description">{item.description}</div>
                   </div>
                 </div>
               ))}
             </div>
           </div>
         ))}
       </div>
     </aside>
   )
}

export default Sidebar