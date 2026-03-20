import React, { memo } from 'react'
import { Handle, Position } from '@xyflow/react'

const BaseNode = memo(({ data, inputs = [], outputs = [] }) => {
  // Create handles from inputs and outputs props
  const inputHandles = inputs.map(input => ({
    id: input.id,
    type: 'target',
    position: Position.Left,
    label: input.label
  }))

  const outputHandles = outputs.map(output => ({
    id: output.id,
    type: 'source',
    position: Position.Right,
    label: output.label
  }))

  const handles = [...inputHandles, ...outputHandles]

  return (
    <div className="custom-node">
      {handles.map((handle, index) => {
        const isInput = handle.position === Position.Left
        const groupHandles = isInput ? inputHandles : outputHandles
        const groupIndex = groupHandles.findIndex(h => h.id === handle.id)
        const positionPercent = ((groupIndex + 1) / (groupHandles.length + 1)) * 100

        return (
          <Handle
            key={handle.id}
            type={handle.type}
            position={handle.position}
            id={handle.id}
            className="node-handle"
            title={handle.label}
            style={{
              ...(handle.position === Position.Left
                ? { left: 0, top: `${positionPercent}%` }
                : { right: 0, top: `${positionPercent}%` }
              ),
              transform: 'translate(0, -50%)'
            }}
          />
        )
      })}

      <div className="node-content">
        <div className="node-label">{data.label}</div>
        {data.value !== undefined && (
          <div className="node-value">{data.value}</div>
        )}

        {/* Render field definitions if present in data */}
        {data.fieldDefinitions && data.fieldDefinitions.length > 0 && (
          <div className="node-fields">
            {/* Group fields by field_type */}
            {['input', 'output', 'monitor'].map(fieldType => {
              const fieldsOfType = data.fieldDefinitions.filter(field => field.field_type === fieldType)
              if (fieldsOfType.length === 0) return null
              
              return (
                <div key={fieldType} className={`node-fields-section node-fields-${fieldType}`}>
                  <div className="node-fields-section-title">
                    {fieldType === 'input' ? 'Inputs:' :
                     fieldType === 'output' ? 'Outputs:' : 'Monitors:'}
                  </div>
                  {fieldsOfType.map(field => (
                    <div key={field.name} className={`node-field node-field-${fieldType}`}>
                      <span className="node-field-name">{field.name}:</span>
                      <span className="node-field-value">
                        {data[field.name] !== undefined ? data[field.name] : 'N/A'}
                        {field.units && ` ${field.units}`}
                      </span>
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
})

BaseNode.displayName = 'BaseNode'

export default BaseNode