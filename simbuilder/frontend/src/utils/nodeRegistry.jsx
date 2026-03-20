/**
 * Frontend node type registry mapping types to React components
 */
import React from 'react'
import InputNode from '../components/nodes/InputNode'
import HouseholdNode from '../components/nodes/HouseholdNode'
import BatteryNode from '../components/nodes/BatteryNode'
import ProcessNode from '../components/nodes/ProcessNode'
import OutputNode from '../components/nodes/OutputNode'
import BaseNode from '../components/nodes/BaseNode'

// Static node types (fallback)
export const nodeTypes = {
  input: InputNode,
  household: HouseholdNode,
  battery: BatteryNode,
  process: ProcessNode,
  output: OutputNode,
}

/**
 * Create a dynamic node component from backend metadata
 */
const createDynamicNodeComponent = (nodeType, metadata) => {
  const DynamicNode = (props) => {
    return React.createElement(BaseNode, {
      ...props,
      inputs: metadata.inputs || [],
      outputs: metadata.outputs || []
    })
  }
  DynamicNode.displayName = `DynamicNode(${nodeType})`
  return DynamicNode
}

/**
 * Register node types from backend API response
 */
export const registerNodeTypesFromBackend = (backendNodeTypes) => {
  if (!backendNodeTypes || typeof backendNodeTypes !== 'object') {
    return nodeTypes
  }

  const updatedNodeTypes = { ...nodeTypes }

  Object.entries(backendNodeTypes).forEach(([nodeType, metadata]) => {
    // Only register if not already present in static registry
    if (!updatedNodeTypes[nodeType]) {
      updatedNodeTypes[nodeType] = createDynamicNodeComponent(nodeType, metadata)
    }
  })

  // Update the main nodeTypes object
  Object.assign(nodeTypes, updatedNodeTypes)

  return updatedNodeTypes
}

/**
 * Helper to merge metadata for a specific node type
 */
export const mergeNodeMetadata = (nodeType, backendMetadata) => {
  if (nodeTypes[nodeType]) {
    // If static component exists, return it as-is
    return nodeTypes[nodeType]
  }

  // Create dynamic component for new node type
  return createDynamicNodeComponent(nodeType, backendMetadata)
}
