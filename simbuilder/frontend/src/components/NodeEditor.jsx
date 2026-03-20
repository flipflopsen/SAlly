import React, { useCallback, useEffect, useState } from 'react'
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Panel,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import Sidebar from './Sidebar'
import NodeConfigEditor from './NodeConfigEditor'
import HelpMenu from './HelpMenu'
import ProjectSelector from './ProjectSelector'
import { apiService } from '../services/api'
import { WebSocketService } from '../services/websocket'
import { nodeTypes } from '../utils/nodeRegistry'

const NodeEditor = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [reactFlowInstance, setReactFlowInstance] = useState(null)
  const [projectId, setProjectId] = useState(null)
  const [currentProject, setCurrentProject] = useState(null)
  const [availableNodeTypes, setAvailableNodeTypes] = useState({})
  const [availableConnectionTypes, setAvailableConnectionTypes] = useState({})
  const [selectedConnectionType, setSelectedConnectionType] = useState('none')
  const [ws, setWs] = useState(null)
  const [loading, setLoading] = useState(true)
  const [projects, setProjects] = useState([])
  const [showConfigEditor, setShowConfigEditor] = useState(false)
  const [selectedNodeForConfig, setSelectedNodeForConfig] = useState(null)
  const [sidebarKey, setSidebarKey] = useState(0)
  const [importSuccessMessage, setImportSuccessMessage] = useState('')
  const [isConnecting, setIsConnecting] = useState(false)
  const [connectionStart, setConnectionStart] = useState(null)
  const [tempEdge, setTempEdge] = useState(null)
  const [showHelpMenu, setShowHelpMenu] = useState(false)

  // Load projects list on mount
  useEffect(() => {
    const loadInitialProjects = async () => {
      try {
        const projectsList = await apiService.getProjects()
        setProjects(projectsList)
        console.log(projectsList)

        // If no project is selected and projects exist, select the first one
        if (projectsList.length > 0) {
          console.log('projectlist length is bigger 0')
          setProjectId(projectsList[0].id)
        } else {
          console.log('projectlist length is smaller 0')
          setLoading(false) // Stop loading if no projects exist
        }
      } catch (error) {
        console.error('Failed to load projects:', error)
        setLoading(false)
      }
    }

    loadInitialProjects()
  }, []) // Empty dependency is fine here

  // Load project data when project changes
  const loadProjectData = useCallback(async (newProjectId) => {
    if (!newProjectId) {
      setLoading(false)
      return
    }

    setLoading(true)
    try {
      const projectData = await apiService.getProject(newProjectId)
      console.log("Project Data:")
      console.log(projectData)

      const nodeTypes = projectData.type_definitions.filter(elem => elem.definition_type == "node").map(nodeType => nodeType.definition_data)
      const connectionTypes = projectData.type_definitions.filter(elem => elem.definition_type == "connection").map(connectionType => connectionType.definition_data)

      console.log(nodeTypes)
      setAvailableNodeTypes(nodeTypes)
      setAvailableConnectionTypes(connectionTypes)

      // Transform nodes to ReactFlow format
      const transformedNodes = projectData.nodes.map(node => ({
        id: node.node_id,
        type: node.node_type,
        position: { x: node.position_x, y: node.position_y },
        data: node.data,
        fieldSchema: node.field_definitions
      }))

      // Transform connections to ReactFlow edges format
      const transformedEdges = projectData.connections.map(connection => ({
        id: connection.connection_id,
        source: connection.source_node,
        target: connection.target_node,
        sourceHandle: connection.source_handle,
        targetHandle: connection.target_handle,
        type: 'smoothstep',
        animated: true
      }))

      setNodes(transformedNodes)
      setEdges(transformedEdges)
      setCurrentProject(projectData)
    } catch (error) {
      console.error('Failed to load project data:', error)
      alert('Failed to load project: ' + error.message)
    } finally {
      setLoading(false)
    }
  }, [setNodes, setEdges])

  // Load project-specific types when project changes
  const loadProjectTypes = useCallback(async (newProjectId) => {
    if (!newProjectId) return

    try {
      const typesData = await apiService.getProjectTypes(newProjectId)
      setAvailableNodeTypes(typesData.node_types || {})
      setAvailableConnectionTypes(typesData.connection_types || {})
      setSidebarKey(prev => prev + 1) // Force sidebar refresh
    } catch (error) {
      console.error('Failed to load project types:', error)
    }
  }, [])

  // Initialize project data when projectId changes
  useEffect(() => {
    if (projectId) {
      loadProjectData(projectId)
      loadProjectTypes(projectId)
    }
  }, [projectId, loadProjectData, loadProjectTypes])

  // Handle project change
  const handleProjectChange = async (newProjectId) => {
    setProjectId(parseInt(newProjectId))
    await loadProjectData(newProjectId)
    await loadProjectTypes(newProjectId)
  }

  // Handle create project
  const handleCreateProject = async (name, description) => {
    const project = await apiService.createProject({ name, description })
    setProjects([...projects, project])
    return project
  }

  // Handle delete project - FIXED: Variable shadowing bug
  const handleDeleteProject = async (deleteProjectId) => {
    try {
      await apiService.deleteProject(deleteProjectId)
      setProjects(projects.filter(p => p.id !== deleteProjectId))

      // If we deleted the current project, select another one or clear selection
      if (deleteProjectId === projectId) {
        const remainingProjects = projects.filter(p => p.id !== deleteProjectId)
        if (remainingProjects.length > 0) {
          await handleProjectChange(remainingProjects[0].id)
        } else {
          // No projects left, clear selection
          setProjectId(null)
          setNodes([])
          setEdges([])
          setCurrentProject(null)
        }
      }
    } catch (error) {
      console.error('Failed to delete project:', error)
      alert('Failed to delete project: ' + error.message)
    }
  }

  // Initialize WebSocket connection (disabled for now)
  useEffect(() => {
    if (!projectId) return

    console.log('WebSocket disabled for now - using HTTP only mode')
    setWs(null)
  }, [projectId])

  // Handle connection creation
  const onConnect = useCallback(
    (params) => {
      const newEdge = {
        ...params,
        id: `e${params.source}-${params.target}-${selectedConnectionType}`,
        type: 'smoothstep',
        animated: true,
        data: { connectionType: selectedConnectionType },
        'data-connection-type': selectedConnectionType
      }

      setEdges((eds) => addEdge(newEdge, eds))

      // Persist to backend with selected connection type
      apiService.createConnection(projectId, {
        connection_id: newEdge.id,
        connection_type: selectedConnectionType,
        source_node_id: params.source,
        target_node_id: params.target,
        source_handle: params.sourceHandle || 'output',
        target_handle: params.targetHandle || 'input',
      }).catch(error => {
        console.error('Failed to create connection:', error)
        // Rollback the edge if backend fails
        setEdges((eds) => eds.filter(e => e.id !== newEdge.id))
      })
    },
    [projectId, selectedConnectionType, setEdges]
  )

  // Handle node drag end
  const onNodeDragStop = useCallback(
    (event, node) => {
      apiService.updateNode(node.id, {
        position_x: node.position.x,
        position_y: node.position.y,
      }).catch(error => {
        console.error('Failed to update node position:', error)
      })
    },
    []
  )

  // Handle node deletion
  const onNodesDelete = useCallback(
    (deleted) => {
      // Remove nodes from frontend ReactFlow state immediately
      setNodes((nds) => nds.filter((n) => !deleted.some(d => d.id === n.id)))
      
      // Also remove any connections that reference the deleted nodes
      setEdges((eds) => eds.filter((edge) =>
        !deleted.some(node => node.id === edge.source) &&
        !deleted.some(node => node.id === edge.target)
      ))
      
      // Delete from backend
      deleted.forEach((node) => {
        apiService.deleteNode(node.id).catch(error => {
          console.error('Failed to delete node:', error)
        })
      })
    },
    [setNodes, setEdges]
  )

  // Handle edge deletion
  const onEdgesDelete = useCallback(
    (deleted) => {
      deleted.forEach((edge) => {
        apiService.deleteConnection(edge.id).catch(error => {
          console.error('Failed to delete connection:', error)
        })
      })
    },
    []
  )

  // Handle drag over for node creation
  const onDragOver = useCallback((event) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  // Handle drop to create new node or connection
  const onDrop = useCallback(
    async (event) => {
      event.preventDefault()

      const type = event.dataTransfer.getData('application/reactflow')
      const isConnection = event.dataTransfer.getData('application/reactflow/isConnection') === 'true'

      if (!type || !reactFlowInstance) return

      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      })

      if (isConnection) {
        setSelectedConnectionType(type)
        console.log('Connection type selected:', type)
      } else {
        const nodeId = `node_${Date.now()}`
        const nodeMetadata = availableNodeTypes[type]

        const newNode = {
          id: nodeId,
          type,
          position,
          data: {
            label: nodeMetadata?.label || type,
            ...nodeMetadata?.defaultData,
          },
        }

        setNodes((nds) => nds.concat(newNode))

        try {
          await apiService.createNode(projectId, {
            node_id: nodeId,
            node_type: type,
            label: newNode.data.label,
            position_x: position.x,
            position_y: position.y,
            data: newNode.data,
          })
        } catch (error) {
          console.error('Failed to create node in backend:', error)
          setNodes((nds) => nds.filter(n => n.id !== nodeId))
          alert('Failed to create node: ' + error.message)
        }
      }
    },
    [reactFlowInstance, projectId, availableNodeTypes, setNodes]
  )

  // Handle connection type selection
  const handleConnectionTypeSelect = useCallback((type) => {
    setSelectedConnectionType(prev => prev === type ? 'none' : type)
  }, [])

  // Handle node double click for config editor
  const onNodeDoubleClick = useCallback((event, node) => {
    setSelectedNodeForConfig(node)
    setShowConfigEditor(true)
  }, [])

  const onNodeContextMenu = useCallback((event, node) => {
    event.preventDefault()
    if (selectedConnectionType && selectedConnectionType !== 'none') {
      setIsConnecting(true)
      setConnectionStart(node)
    }
  }, [selectedConnectionType])

  const onNodeClick = useCallback((event, node) => {
    if (isConnecting && connectionStart && connectionStart.id !== node.id) {
      const newEdge = {
        source: connectionStart.id,
        target: node.id,
        id: `e${connectionStart.id}-${node.id}-${selectedConnectionType}`,
        type: 'smoothstep',
        animated: true,
        data: { connectionType: selectedConnectionType },
        'data-connection-type': selectedConnectionType
      }

      setEdges((eds) => addEdge(newEdge, eds))

      apiService.createConnection(projectId, {
        connection_id: newEdge.id,
        connection_type: selectedConnectionType,
        source_node_id: connectionStart.id,
        target_node_id: node.id,
        source_handle: 'output',
        target_handle: 'input'
      }).catch(error => {
        console.error('Failed to create connection:', error)
        setEdges((eds) => eds.filter(e => e.id !== newEdge.id))
      })

      setIsConnecting(false)
      setConnectionStart(null)
    }
  }, [isConnecting, connectionStart, selectedConnectionType, projectId, setEdges])

  const onEdgeDoubleClick = useCallback((event, edge) => {
    event.preventDefault()
    setEdges((eds) => eds.filter((e) => e.id !== edge.id))
    apiService.deleteConnection(edge.id).catch(err => {
      console.error('Failed to delete connection:', err)
    })
  }, [setEdges])

  const onPaneClick = useCallback(() => {
    if (isConnecting) {
      setIsConnecting(false)
      setConnectionStart(null)
    }
  }, [isConnecting])

  // Handle save node config
  const handleSaveNodeConfig = useCallback(async (fieldDefinitions) => {
    try {
      await apiService.updateNodeFields(selectedNodeForConfig.id, fieldDefinitions)
      setNodes((nds) => nds.map((n) =>
        n.id === selectedNodeForConfig.id
          ? { ...n, data: { ...n.data, fieldDefinitions } }
          : n
      ))
      setShowConfigEditor(true)
      alert('Configuration saved successfully!')
    } catch (error) {
      console.error('Failed to save node config:', error)
      alert('Failed to save configuration: ' + error.message)
    }
  }, [selectedNodeForConfig, setNodes])

  // Handle export type definitions
  const handleExportTypeDefinitions = useCallback(async () => {
    try {
      const typeData = await apiService.exportTypeDefinitions()
      const blob = new Blob([JSON.stringify(typeData, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'type_definitions.json'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Export failed:', error)
      alert('Export failed: ' + error.message)
    }
  }, [])

  // Handle import type definitions
  const handleImportTypeDefinitions = useCallback(async (event) => {
    const file = event.target.files[0]
    if (!file) return

    setLoading(true)
    const reader = new FileReader()
    reader.onload = async (e) => {
      try {
        const typeData = JSON.parse(e.target.result)
        const response = await apiService.importTypeDefinitions(typeData, projectId)
        const message = `Import successful! Imported ${response.imported_nodes || 0} new nodes and ${response.imported_connections || 0} new connections.`
        setImportSuccessMessage(message)
        setTimeout(() => setImportSuccessMessage(''), 3000)

        // Reload types
        setTimeout(async () => {
          setSidebarKey(prev => prev + 1)
          try {
            const [nodeTypes, connectionTypes] = await Promise.all([
              apiService.getNodeTypes(),
              apiService.getConnectionTypes()
            ])
            setAvailableNodeTypes(nodeTypes)
            setAvailableConnectionTypes(connectionTypes)
          } catch (err) {
            console.error('Error reloading types:', err)
          }
        }, 150)
      } catch (error) {
        console.error('Import failed:', error)
        const errorDetails = error.response?.data?.details ? ` Details: ${error.response.data.details}` : ''
        alert('Import failed: ' + error.message + errorDetails)
      } finally {
        setLoading(false)
      }
    }
    reader.readAsText(file)
    event.target.value = ''
  }, [projectId])

  // Handle export graph
  const handleExportGraph = useCallback(async () => {
    if (!projectId) {
      alert('No project selected')
      return
    }
    
    try {
      setLoading(true)
      const graphData = await apiService.exportProject(projectId)
      
      // Create download link for YAML file
      const blob = new Blob([graphData], { type: 'text/yaml' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `project_${projectId}_graph.yaml`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      
    } catch (error) {
      console.error('Export failed:', error)
      alert('Export failed: ' + error.message)
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isConnecting) {
        setIsConnecting(false)
        setConnectionStart(null)
      }
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [isConnecting])

  useEffect(() => {
    const handleHelpKey = (e) => {
      if (e.key === '?' || e.key === 'F1') {
        e.preventDefault()
        setShowHelpMenu(prev => !prev)
      }
    }
    window.addEventListener('keydown', handleHelpKey)
    return () => window.removeEventListener('keydown', handleHelpKey)
  }, [])
  useEffect(() => {
    const handleDeleteKey = (e) => {
      if ((e.key === 'Delete' || e.key === 'Backspace') && reactFlowInstance) {
        e.preventDefault()
        const allNodes = reactFlowInstance.getNodes()
        const selectedNodes = allNodes.filter(node => node.selected)
        if (selectedNodes.length > 0) {
          onNodesDelete(selectedNodes)
        }
      }
    }
    window.addEventListener('keydown', handleDeleteKey)
    return () => window.removeEventListener('keydown', handleDeleteKey)
  }, [reactFlowInstance, onNodesDelete])


  return (
    <div className="node-editor" style={{ width: '100%', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '10px', borderBottom: '1px solid #ddd', background: '#f5f5f5' }}>
        <ProjectSelector
          currentProjectId={projectId}
          projects={projects}
          onProjectChange={handleProjectChange}
          onCreateProject={handleCreateProject}
          onDeleteProject={handleDeleteProject}
        />
      </div>

      {!projectId ? (
        <div className="no-project-selected" style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          color: '#666'
        }}>
          <h2>Welcome to Node Graph Editor</h2>
          <p>Select or create a project to get started.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          <Sidebar
            key={sidebarKey}
            nodeTypes={availableNodeTypes}
            connectionTypes={availableConnectionTypes}
            selectedConnectionType={selectedConnectionType}
            onConnectionTypeSelect={handleConnectionTypeSelect}
          />

          <div className={`reactflow-wrapper ${isConnecting ? 'connecting' : ''}`} style={{ flex: 1, position: 'relative' }}>
            {loading ? (
              <div className="loading-container" style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%'
              }}>
                <div className="loading-spinner" style={{
                  border: '4px solid #f3f3f3',
                  borderTop: '4px solid #3498db',
                  borderRadius: '50%',
                  width: '40px',
                  height: '40px',
                  animation: 'spin 1s linear infinite'
                }}></div>
                <p>Loading project...</p>
              </div>
            ) : (
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onNodeDragStop={onNodeDragStop}
                onNodesDelete={onNodesDelete}
                onEdgesDelete={onEdgesDelete}
                onInit={setReactFlowInstance}
                onDrop={onDrop}
                onDragOver={onDragOver}
                onNodeDoubleClick={onNodeDoubleClick}
                onNodeContextMenu={onNodeContextMenu}
                onNodeClick={onNodeClick}
                onEdgeDoubleClick={onEdgeDoubleClick}
                onPaneClick={onPaneClick}
                nodeTypes={nodeTypes}
                fitView
                snapToGrid
                snapGrid={[15, 15]}
                className={isConnecting ? 'connecting' : ''}
              >
                <Background color="#BADBA2" gap={16} />
                <Controls />
                <MiniMap
                  nodeColor="#80EF80"
                  maskColor="rgba(226, 240, 163, 0.3)"
                />
                <Panel position="top-left">
                  <div className="panel-controls">
                    <div className="panel-buttons">
                      <button className="export-button" onClick={handleExportTypeDefinitions}>
                        Export Types
                      </button>
                      <button className="export-button" onClick={handleExportGraph}>
                        Export Graph
                      </button>
                      <label className="import-button">
                        Import Types
                        <input
                          type="file"
                          accept=".json"
                          onChange={handleImportTypeDefinitions}
                          style={{ display: 'none' }}
                        />
                      </label>
                      <button className="help-button" onClick={() => setShowHelpMenu(true)}>
                        Help (?)
                      </button>
                    </div>
                  </div>
                  <div className="panel-info">
                    <h3>Node Graph Editor</h3>
                    <p>Drag nodes from sidebar • Connect ports • Drag to move</p>
                  </div>
                  {importSuccessMessage && (
                    <div className="success-message" style={{
                      background: '#4CAF50',
                      color: 'white',
                      padding: '8px',
                      borderRadius: '4px',
                      marginTop: '8px'
                    }}>
                      {importSuccessMessage}
                    </div>
                  )}
                  {isConnecting && connectionStart && (
                    <div className="connection-mode-indicator" style={{
                      background: '#2196F3',
                      color: 'white',
                      padding: '8px',
                      borderRadius: '4px',
                      marginTop: '8px'
                    }}>
                      Connecting from {connectionStart.data.label}... Click target node
                    </div>
                  )}
                </Panel>
              </ReactFlow>
            )}
          </div>

          <NodeConfigEditor
            isOpen={showConfigEditor}
            nodeData={selectedNodeForConfig}
            availableNodeTypes={availableNodeTypes}
            onClose={() => setShowConfigEditor(false)}
            onSave={handleSaveNodeConfig}
          />
          <HelpMenu isOpen={showHelpMenu} onClose={() => setShowHelpMenu(false)} />
        </div>
      )}

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

export default NodeEditor
