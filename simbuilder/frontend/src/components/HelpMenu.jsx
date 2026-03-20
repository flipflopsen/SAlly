import React, { useEffect } from 'react'

const HelpMenu = ({ isOpen, onClose }) => {
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    if (isOpen) {
      window.addEventListener('keydown', handleEscape)
    }
    return () => window.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content help-menu-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Help & Keyboard Shortcuts</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <div className="help-section">
            <h3>🖱️ Node Operations</h3>
            <div className="help-item">
              <div className="help-item-title">Drag & Drop</div>
              <div className="help-item-description">Drag nodes from sidebar to canvas to create new nodes</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Move</div>
              <div className="help-item-description">Click and drag nodes to reposition them</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Delete</div>
              <div className="help-item-description">Select node(s) and press <span className="help-shortcut">Delete</span> or <span className="help-shortcut">Backspace</span> key</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Configure</div>
              <div className="help-item-description">Double-click a node to open configuration editor</div>
            </div>
          </div>

          <div className="help-section">
            <h3>🔗 Connection Operations</h3>
            <div className="help-item">
              <div className="help-item-title">Select Type</div>
              <div className="help-item-description">Click a connection type in sidebar to select it (click again to deselect)</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Create Connection (Method 1)</div>
              <div className="help-item-description">Drag from a node's output handle to another node's input handle</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Create Connection (Method 2)</div>
              <div className="help-item-description">Select a connection type, right-click source node, then left-click target node</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Delete Connection</div>
              <div className="help-item-description">Double-click on a connection line to delete it</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Cancel Connection</div>
              <div className="help-item-description">Press <span className="help-shortcut">Escape</span> key to cancel connection mode</div>
            </div>
          </div>

          <div className="help-section">
            <h3>🔗 Connection Types</h3>
            <div className="help-item">
              <div className="help-item-title">Input</div>
              <div className="help-item-description">Green - Data input connections</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Output</div>
              <div className="help-item-description">Red - Data output connections</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Monitor</div>
              <div className="help-item-description">Blue - Monitoring connections</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">None</div>
              <div className="help-item-description">Default state - no connection type selected</div>
            </div>
          </div>

          <div className="help-section">
            <h3>📁 Project Operations</h3>
            <div className="help-item">
              <div className="help-item-title">Switch Project</div>
              <div className="help-item-description">Use project selector dropdown in top-left corner</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Create Project</div>
              <div className="help-item-description">Click 'Create New Project' in project selector</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Export Types</div>
              <div className="help-item-description">Click 'Export Types' button to save type definitions</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Import Types</div>
              <div className="help-item-description">Click 'Import Types' button to load type definitions</div>
            </div>
          </div>

          <div className="help-section">
            <h3>⌨️ Keyboard Shortcuts</h3>
            <div className="help-item">
              <div className="help-item-title">?</div>
              <div className="help-item-description">Toggle this help menu</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">F1</div>
              <div className="help-item-description">Toggle this help menu</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Escape</div>
              <div className="help-item-description">Cancel connection mode or close dialogs</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Delete/Backspace</div>
              <div className="help-item-description">Delete selected nodes or edges</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Ctrl+Z</div>
              <div className="help-item-description">Undo (if implemented)</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Ctrl+Y</div>
              <div className="help-item-description">Redo (if implemented)</div>
            </div>
          </div>

          <div className="help-section">
            <h3>🖼️ Canvas Operations</h3>
            <div className="help-item">
              <div className="help-item-title">Pan</div>
              <div className="help-item-description">Click and drag on empty canvas area</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Zoom</div>
              <div className="help-item-description">Use mouse wheel or pinch gesture</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Fit View</div>
              <div className="help-item-description">Use controls in bottom-right corner</div>
            </div>
            <div className="help-item">
              <div className="help-item-title">Snap to Grid</div>
              <div className="help-item-description">Nodes automatically snap to 15x15 grid</div>
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="close-button" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}

export default HelpMenu