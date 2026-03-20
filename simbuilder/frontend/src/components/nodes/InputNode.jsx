import React from 'react'
import BaseNode from './BaseNode'

const InputNode = (props) => {
  const { data } = props

  // Use dynamic metadata from backend if available, otherwise fallback to hardcoded
  const inputs = data.inputs || []
  const outputs = data.outputs || [{ id: 'output', label: 'Output' }]

  return (
    <BaseNode
      {...props}
      inputs={inputs}
      outputs={outputs}
    />
  )
}

export default InputNode
