import React from 'react'
import BaseNode from './BaseNode'

const HouseholdNode = (props) => {
  const { data } = props

  // Use dynamic metadata from backend if available, otherwise fallback to hardcoded
  const inputs = data.inputs || [{ id: 'electricity', label: 'Electricity' }]
  const outputs = data.outputs || [{ id: 'load', label: 'Load' }]

  return (
    <BaseNode
      {...props}
      inputs={inputs}
      outputs={outputs}
    />
  )
}

export default HouseholdNode