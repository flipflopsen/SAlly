import React from 'react'
import BaseNode from './BaseNode'

const OutputNode = (props) => {
  const { data } = props

  // Use dynamic metadata from backend if available, otherwise fallback to hardcoded
  const inputs = data.inputs || [{ id: 'input', label: 'Input' }]
  const outputs = data.outputs || [] // Output nodes have no outputs

  return (
    <BaseNode
      {...props}
      inputs={inputs}
      outputs={outputs}
    />
  )
}

export default OutputNode
