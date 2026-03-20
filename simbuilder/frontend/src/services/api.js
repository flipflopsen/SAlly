/**
 * HTTP API service for REST communication with Django backend
 */
import axios from 'axios'

const API_BASE_URL = '/api'

class ApiService {
  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    })
  }

  /**
   * Get all available node types from backend
   */
  async getNodeTypes() {
    try {
      const response = await this.client.get('/projects/node_types/')
      return response.data
    } catch (error) {
      console.error('Error fetching node types:', error)
      return {}
    }
  }

  /**
   * Get all available connection types from backend
   */
  async getConnectionTypes() {
    try {
      const response = await this.client.get('/projects/connection_types/')
      return response.data
    } catch (error) {
      console.error('Error fetching connection types:', error)
      return {}
    }
  }

  /**
   * Get all projects
   */
  async getProjects() {
    try {
      const response = await this.client.get('/projects/')
      console.log(response.data)
      return response.data.results
    } catch (error) {
      console.error('Error fetching projects:', error)
      return []
    }
  }

  /**
   * Get project with all nodes and connections
   */
  async getProject(projectId) {
    const response = await this.client.get(`/projects/${projectId}/`)
    return response.data
  }

  /**
   * Create new node in project
   */
  async createNode(projectId, nodeData) {
    const response = await this.client.post(
      `/projects/${projectId}/add_node/`,
      nodeData
    )
    return response.data
  }

  /**
   * Update existing node
   */
  async updateNode(nodeId, updates) {
    const response = await this.client.patch(`/nodes/${nodeId}/`, updates)
    return response.data
  }

  /**
   * Delete node
   */
  async deleteNode(nodeId) {
    await this.client.delete(`/nodes/${nodeId}/`)
  }

  /**
   * Create connection between nodes
   */
  async createConnection(projectId, connectionData) {
    const response = await this.client.post(
      `/projects/${projectId}/add_connection/`,
      connectionData
    )
    return response.data
  }

  /**
   * Delete connection
   */
  async deleteConnection(connectionId) {
    await this.client.delete(`/connections/${connectionId}/`)
  }

  /**
   * Export project graph data in YAML format as a Blob for download
   * @param {number} projectId - The project ID to export
   * @returns {Promise<Blob>} Project graph data in YAML format as a Blob
   */
  async exportProject(projectId) {
    try {
      const response = await this.client.get(`/projects/${projectId}/export_graph/`, {
        responseType: 'blob'
      })
      return response.data
    } catch (error) {
      console.error('Error exporting project:', error)
      throw error
    }
  }

  /**
   * Import project graph data
   */
  async importProject(projectId, importData) {
    try {
      const response = await this.client.post(
        `/projects/${projectId}/import_graph/`,
        importData
      )
      return response.data
    } catch (error) {
      console.error('Error importing project:', error)
      throw error
    }
  }

  /**
   * Create new project
   */
  async createProject(projectData) {
    try {
      const response = await this.client.post('/projects/', projectData)
      return response.data
    } catch (error) {
      console.error('Error creating project:', error)
      throw error
    }
  }

  /**
   * Update existing project
   */
  async updateProject(projectId, updates) {
    try {
      const response = await this.client.patch(`/projects/${projectId}/`, updates)
      return response.data
    } catch (error) {
      console.error('Error updating project:', error)
      throw error
    }
  }

  /**
   * Delete project
   */
  async deleteProject(projectId) {
    try {
      await this.client.delete(`/projects/${projectId}/`)
    } catch (error) {
      console.error('Error deleting project:', error)
      throw error
    }
  }

  /**
   * Export type definitions for nodes and connections
   */
  async exportTypeDefinitions(projectId = null) {
    try {
      const url = projectId
        ? `/projects/export_type_definitions/?project_id=${projectId}`
        : '/projects/export_type_definitions/'
      const response = await this.client.get(url)
      return response.data
    } catch (error) {
      console.error('Error exporting type definitions:', error)
      return {}
    }
  }

  /**
   * Import type definitions for nodes and connections
   */
  async importTypeDefinitions(typeData, projectId = null) {
    try {
      const payload = projectId ? { ...typeData, project_id: projectId } : typeData
      const response = await this.client.post('/projects/import_type_definitions/', payload)
      return response.data
    } catch (error) {
      console.error('Error importing type definitions:', error)
      throw error
    }
  }

  /**
   * Get project-specific type definitions
   */
  async getProjectTypes(projectId) {
    try {
      const response = await this.client.get(`/projects/${projectId}/type_definitions/`)
      return response.data
    } catch (error) {
      console.error('Error fetching project types:', error)
      return { node_types: {}, connection_types: {} }
    }
  }

  /**
   * Update node fields configuration
   */
  async updateNodeFields(nodeId, fieldDefinitions) {
    try {
      const response = await this.client.patch(`/nodes/${nodeId}/update_node_fields/`, {
        field_definitions: fieldDefinitions
      })
      return response.data
    } catch (error) {
      console.error('Error updating node fields:', error)
      throw error
    }
  }
}

export const apiService = new ApiService()