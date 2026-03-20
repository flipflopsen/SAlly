import React from 'react'
import BaseNode from './BaseNode'

const ProcessNode = (props) => {
  const { data } = props

  // Use dynamic metadata from backend if available, otherwise fallback to hardcoded
  const inputs = data.inputs || [
    { id: 'input1', label: 'Input 1' },
    { id: 'input2', label: 'Input 2' }
  ]
  const outputs = data.outputs || [
    { id: 'output', label: 'Result' }
  ]

  return (
    <BaseNode
      {...props}
      inputs={inputs}
      outputs={outputs}
    />
  )
}

export default ProcessNode
