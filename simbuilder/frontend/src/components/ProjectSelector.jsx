import React, { useState, useEffect } from 'react'
import {apiService} from "../services/api.js";
// Note: apiService import is unused - remove if not needed elsewhere

const ProjectSelector = ({ currentProjectId, projects, onProjectChange, onCreateProject, onDeleteProject }) => {
  const [showDropdown, setShowDropdown] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectDescription, setNewProjectDescription] = useState('')

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (showDropdown && !event.target.closest('.project-selector')) {
        setShowDropdown(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showDropdown])

  const handleProjectSelect = async (projectId) => {
    setShowDropdown(false)
    if (projectId !== currentProjectId) {
      await onProjectChange(projectId)
    }
  }

  const handleProjectDelete = async (projectId, e) => {
    e.stopPropagation()
    if (window.confirm('Are you sure you want to delete this project? This action cannot be undone.')) {
      try {
        await onDeleteProject(projectId)
      } catch (error) {
        alert('Failed to delete project: ' + error.message)
      }
    }
  }

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) {
      alert('Project name is required')
      return
    }

    try {
      const project = await onCreateProject(newProjectName.trim(), newProjectDescription.trim())
      setShowCreateModal(false)
      setNewProjectName(newProjectName.trim())
      setNewProjectDescription(newProjectDescription.trim())
      await onProjectChange(project.id)
    } catch (error) {
      alert('Failed to create project: ' + error.message)
    }
  }


  const currentProject = Array.isArray(projects)
  ? projects.find(p => p.id === currentProjectId)
  : null


  return (
    <div className="project-selector" style={{ position: 'relative', display: 'inline-block' }}>
      <button
        className="project-selector-button"
        onClick={() => setShowDropdown(!showDropdown)}
        style={{
          padding: '8px 16px',
          border: '1px solid #ddd',
          borderRadius: '4px',
          background: 'white',
          cursor: 'pointer',
          fontSize: '14px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}
      >
        {currentProject ? currentProject.name : 'Select Project'}
        <span style={{ fontSize: '10px' }}>▼</span>
      </button>

      {showDropdown && (
        <div
          className="project-dropdown"
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            marginTop: '4px',
            minWidth: '200px',
            background: 'white',
            border: '1px solid #ddd',
            borderRadius: '4px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            zIndex: 1000,
            maxHeight: '300px',
            overflowY: 'auto'
          }}
        >
          {projects && projects.length > 0 ? (
            projects.map(project => (
              <div
                key={project.id}
                className={`project-item ${project.id === currentProjectId ? 'active' : ''}`}
                onClick={() => handleProjectSelect(project.id)}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '8px 12px',
                  cursor: 'pointer',
                  borderBottom: '1px solid #f0f0f0',
                  backgroundColor: project.id === currentProjectId ? '#f0f8ff' : 'transparent',
                  transition: 'background-color 0.2s'
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f5f5f5'}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = project.id === currentProjectId ? '#f0f8ff' : 'transparent'
                }}
              >
                <span>{project.name}</span>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  {project.id === currentProjectId && <span style={{ color: '#4CAF50' }}>✓</span>}
                  <button
                    onClick={(e) => handleProjectDelete(project.id, e)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#ff4444',
                      cursor: 'pointer',
                      fontSize: '16px',
                      padding: '2px 4px',
                      lineHeight: 1
                    }}
                    title="Delete project"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))
          ) : (
            <div style={{ padding: '12px', color: '#999', textAlign: 'center' }}>
              No projects available
            </div>
          )}

          <div style={{ borderTop: '1px solid #eee', margin: '4px 0' }}></div>

          <button
            className="create-project-button"
            onClick={() => {
              setShowDropdown(false)
              setShowCreateModal(true)
            }}
            style={{
              width: '100%',
              padding: '10px 12px',
              border: 'none',
              background: 'transparent',
              color: '#4CAF50',
              cursor: 'pointer',
              textAlign: 'left',
              fontSize: '14px',
              fontWeight: 'bold'
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f5f5f5'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
          >
            + Create New Project
          </button>
        </div>
      )}

      {showCreateModal && (
        <div
          className="modal-overlay"
          onClick={() => setShowCreateModal(false)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 2000
          }}
        >
          <div
            className="create-project-modal"
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'white',
              padding: '24px',
              borderRadius: '8px',
              minWidth: '400px',
              maxWidth: '90vw',
              boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
            }}
          >
            <h3 style={{ marginTop: 0, marginBottom: '20px' }}>Create New Project</h3>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>
                Project Name *
              </label>
              <input
                type="text"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleCreateProject()}
                placeholder="Enter project name"
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  fontSize: '14px',
                  boxSizing: 'border-box'
                }}
                autoFocus
              />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>
                Description (Optional)
              </label>
              <textarea
                value={newProjectDescription}
                onChange={(e) => setNewProjectDescription(e.target.value)}
                placeholder="Enter project description"
                rows="3"
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  resize: 'vertical',
                  fontSize: '14px',
                  fontFamily: 'inherit',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowCreateModal(false)}
                style={{
                  padding: '8px 16px',
                  border: '1px solid #ddd',
                  background: 'white',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleCreateProject}
                style={{
                  padding: '8px 16px',
                  border: 'none',
                  background: '#4CAF50',
                  color: 'white',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ProjectSelector
