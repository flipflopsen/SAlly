import React from 'react'
import BaseNode from './BaseNode'

const BatteryNode = (props) => {
  const { data } = props

  // Use dynamic metadata from backend if available, otherwise fallback to hardcoded
  const inputs = data.inputs || [
    { id: 'charge', label: 'Charge' },
    { id: 'grid_power', label: 'Grid Power' }
  ]
  const outputs = data.outputs || [
    { id: 'discharge', label: 'Discharge' },
    { id: 'soc', label: 'State of Charge' }
  ]

  return (
    <BaseNode
      {...props}
      inputs={inputs}
      outputs={outputs}
    />
  )
}

export default BatteryNode