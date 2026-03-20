import React, { useState, useEffect } from 'react'
import { apiService } from '../services/api'

const NodeConfigEditor = ({ isOpen, onClose, nodeData, onSave, availableNodeTypes }) => {
  const [fieldDefinitions, setFieldDefinitions] = useState([])
  const [errors, setErrors] = useState({})

  // Initialize fieldDefinitions from nodeData, merging with default schema
  useEffect(() => {
    if (isOpen && nodeData) {
      // Start with existing field definitions from node data
      console.log(availableNodeTypes[nodeData.type])
      let existingFields = availableNodeTypes[nodeData.type]?.fieldSchema || []
      console.log(availableNodeTypes)
      
      // If availableNodeTypes is provided and node type exists, merge with default schema
      if (availableNodeTypes && nodeData.type && availableNodeTypes[nodeData.type]) {
        const defaultSchema = availableNodeTypes[nodeData.type].fieldSchema || []
        
        // Create a map of existing fields by name for quick lookup
        const existingFieldsMap = {}
        existingFields.forEach(field => {
          existingFieldsMap[field.name] = field
        })
        
        // Merge default schema with existing fields, giving priority to existing
        const mergedFields = []
        const allFieldNames = new Set([...defaultSchema.map(f => f.name), ...existingFields.map(f => f.name)])
        
        allFieldNames.forEach(fieldName => {
          const existingField = existingFieldsMap[fieldName]
          const defaultField = defaultSchema.find(f => f.name === fieldName)
          
          if (existingField) {
            // Use existing field definition, but update missing properties from default
            const mergedField = { ...defaultField, ...existingField }
            mergedFields.push(mergedField)
          } else if (defaultField) {
            // Use default field definition
            mergedFields.push(defaultField)
          }
        })
        
        existingFields = mergedFields
      }
      
      setFieldDefinitions(existingFields)
      availableNodeTypes[nodeData.type].fieldSchema = existingFields
      setErrors({})
    }
  }, [isOpen, nodeData, availableNodeTypes])

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = 'unset'
    }

    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [isOpen])

  const handleFieldChange = (index, field, value) => {
    const updatedFields = [...fieldDefinitions]
    updatedFields[index][field] = value

    // Clear min/max values when switching away from number type
    if (field === 'data_type' && value !== 'number') {
      updatedFields[index].min_value = ''
      updatedFields[index].max_value = ''
    }

    setFieldDefinitions(updatedFields)
    availableNodeTypes[nodeData.type].fieldSchema = updatedFields

    // Clear error for this field
    if (errors[`${index}-${field}`]) {
      setErrors(prev => ({
        ...prev,
        [`${index}-${field}`]: ''
      }))
    }
  }

  const addField = () => {
    setFieldDefinitions([...fieldDefinitions, {
      name: '',
      field_type: 'monitor',
      data_type: 'string',
      units: '',
      min_value: '',
      max_value: '',
      default_value: '',
      required: false,
      description: ''
    }])
    console.log(fieldDefinitions)
  }

  const deleteField = (index) => {
    const updatedFields = fieldDefinitions.filter((_, i) => i !== index)
    setFieldDefinitions(updatedFields)
  }

  const validateForm = () => {
    const newErrors = {}
    const names = new Set()

    fieldDefinitions.forEach((field, index) => {
      // Validate field name
      if (!field.name.trim()) {
        newErrors[`${index}-name`] = 'Field name is required'
      } else if (names.has(field.name.trim())) {
        newErrors[`${index}-name`] = 'Field name must be unique'
      } else {
        names.add(field.name.trim())
      }

      // Validate number-specific fields
      if (field.data_type === 'number') {
        if (field.min_value !== '' && isNaN(Number(field.min_value))) {
          newErrors[`${index}-min_value`] = 'Min value must be a number'
        }
        if (field.max_value !== '' && isNaN(Number(field.max_value))) {
          newErrors[`${index}-max_value`] = 'Max value must be a number'
        }
        if (field.min_value !== '' && field.max_value !== '' && Number(field.min_value) >= Number(field.max_value)) {
          newErrors[`${index}-min_value`] = 'Min value must be less than max value'
        }
        if (field.default_value !== '' && isNaN(Number(field.default_value))) {
          newErrors[`${index}-default_value`] = 'Default value must be a number'
        }
      }

      // Validate array/object default values
      if ((field.data_type === 'array' || field.data_type === 'object') && field.default_value !== '') {
        try {
          JSON.parse(field.default_value)
        } catch (e) {
          newErrors[`${index}-default_value`] = 'Must be valid JSON'
        }
      }
    })

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = (e) => {
    e.preventDefault()

    if (!validateForm()) {
      return
    }

    // Transform field names to match backend expectations
    const transformedFields = fieldDefinitions.map(f => ({
      field_name: f.name,
      field_type: f.field_type,
      data_type: f.data_type,
      units: f.units || '',
      min_value: f.data_type === 'number' ? f.min_value : '',
      max_value: f.data_type === 'number' ? f.max_value : '',
      default_value: f.default_value,
      required: f.required,
      description: f.description || ''
    }))

    onSave(transformedFields)
  }

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  const renderDefaultValueInput = (field, index) => {
    switch (field.data_type) {
      case 'boolean':
        return (
          <input
            type="checkbox"
            checked={field.default_value === true || field.default_value === 'true'}
            onChange={(e) => handleFieldChange(index, 'default_value', e.target.checked)}
            style={{ width: 'auto', marginRight: '8px' }}
          />
        )
      case 'number':
        return (
          <input
            type="number"
            step="any"
            value={field.default_value}
            onChange={(e) => handleFieldChange(index, 'default_value', e.target.value)}
            className={errors[`${index}-default_value`] ? 'error' : ''}
            placeholder="Default value"
          />
        )
      case 'array':
      case 'object':
        return (
          <textarea
            value={field.default_value}
            onChange={(e) => handleFieldChange(index, 'default_value', e.target.value)}
            className={errors[`${index}-default_value`] ? 'error' : ''}
            placeholder={field.data_type === 'array' ? '["item1", "item2"]' : '{"key": "value"}'}
            rows="2"
          />
        )
      default:
        return (
          <input
            type="text"
            value={field.default_value}
            onChange={(e) => handleFieldChange(index, 'default_value', e.target.value)}
            placeholder="Default value"
          />
        )
    }
  }

  const shouldShowUnits = (dataType) => {
    return ['number', 'string'].includes(dataType)
  }

  const shouldShowMinMax = (dataType) => {
    return dataType === 'number'
  }

  if (!isOpen) {
    return null
  }

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="config-editor-modal">
        <form onSubmit={handleSubmit}>
          <div className="modal-content">
            <div className="modal-header">
              <h3>Edit Node Configuration</h3>
              <p style={{ fontSize: '14px', color: '#666', margin: '8px 0 0 0' }}>
                Configure fields for: <strong>{nodeData?.data?.label || 'Node'}</strong>
              </p>
            </div>

            <div className="modal-body">
              <div className="field-list">
                {fieldDefinitions.map((field, index) => (
                  <div key={index} className="field-row">
                    <div className="field-input-group">
                      <label>Field Name *</label>
                      <input
                        type="text"
                        value={field.name}
                        onChange={(e) => handleFieldChange(index, 'name', e.target.value)}
                        className={errors[`${index}-name`] ? 'error' : ''}
                        placeholder="Field name"
                      />
                      {errors[`${index}-name`] && <span className="error-message">{errors[`${index}-name`]}</span>}
                    </div>

                    <div className="field-input-group">
                      <label>Field Type</label>
                      <select
                        value={field.field_type}
                        onChange={(e) => handleFieldChange(index, 'field_type', e.target.value)}
                      >
                        <option value="input">Input</option>
                        <option value="output">Output</option>
                        <option value="monitor">Monitor</option>
                      </select>
                    </div>

                    <div className="field-input-group">
                      <label>Data Type</label>
                      <select
                        value={field.data_type}
                        onChange={(e) => handleFieldChange(index, 'data_type', e.target.value)}
                      >
                        <option value="string">String</option>
                        <option value="number">Number</option>
                        <option value="boolean">Boolean</option>
                        <option value="array">Array</option>
                        <option value="object">Object</option>
                      </select>
                    </div>

                    {shouldShowUnits(field.data_type) && (
                      <div className="field-input-group">
                        <label>Units {field.data_type === 'number' && '(optional)'}</label>
                        <input
                          type="text"
                          value={field.units}
                          onChange={(e) => handleFieldChange(index, 'units', e.target.value)}
                          placeholder="e.g., V, A, °C, meters"
                        />
                      </div>
                    )}

                    {shouldShowMinMax(field.data_type) && (
                      <>
                        <div className="field-input-group">
                          <label>Min Value</label>
                          <input
                            type="number"
                            step="any"
                            value={field.min_value}
                            onChange={(e) => handleFieldChange(index, 'min_value', e.target.value)}
                            className={errors[`${index}-min_value`] ? 'error' : ''}
                            placeholder="Minimum"
                          />
                          {errors[`${index}-min_value`] && <span className="error-message">{errors[`${index}-min_value`]}</span>}
                        </div>

                        <div className="field-input-group">
                          <label>Max Value</label>
                          <input
                            type="number"
                            step="any"
                            value={field.max_value}
                            onChange={(e) => handleFieldChange(index, 'max_value', e.target.value)}
                            className={errors[`${index}-max_value`] ? 'error' : ''}
                            placeholder="Maximum"
                          />
                          {errors[`${index}-max_value`] && <span className="error-message">{errors[`${index}-max_value`]}</span>}
                        </div>
                      </>
                    )}

                    <div className="field-input-group">
                      <label>
                        Default Value
                        {field.data_type === 'array' && ' (JSON Array)'}
                        {field.data_type === 'object' && ' (JSON Object)'}
                      </label>
                      {renderDefaultValueInput(field, index)}
                      {errors[`${index}-default_value`] && <span className="error-message">{errors[`${index}-default_value`]}</span>}
                    </div>

                    <div className="field-input-group">
                      <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={field.required}
                          onChange={(e) => handleFieldChange(index, 'required', e.target.checked)}
                          style={{ width: 'auto', marginRight: '8px' }}
                        />
                        Required
                      </label>
                    </div>

                    <div className="field-input-group">
                      <label>Description</label>
                      <textarea
                        value={field.description}
                        onChange={(e) => handleFieldChange(index, 'description', e.target.value)}
                        placeholder="Field description"
                        rows="2"
                      />
                    </div>

                    <div className="field-actions">
                      <button
                        type="button"
                        onClick={() => deleteField(index)}
                        style={{
                          background: '#ff4444',
                          color: 'white',
                          border: 'none',
                          padding: '6px 12px',
                          borderRadius: '4px',
                          cursor: 'pointer'
                        }}
                      >
                        Delete Field
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {fieldDefinitions.length === 0 && (
                <div style={{
                  textAlign: 'center',
                  padding: '40px',
                  color: '#999',
                  border: '2px dashed #ddd',
                  borderRadius: '8px',
                  margin: '20px 0'
                }}>
                  <p>No fields defined yet. Click "Add Field" to start.</p>
                </div>
              )}

              <button
                type="button"
                className="add-field-button"
                onClick={addField}
                style={{
                  width: '100%',
                  padding: '12px',
                  background: '#4CAF50',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 'bold',
                  marginTop: '16px'
                }}
              >
                + Add Field
              </button>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                onClick={onClose}
                style={{
                  padding: '10px 20px',
                  background: '#fff',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                style={{
                  padding: '10px 20px',
                  background: '#2196F3',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 'bold'
                }}
              >
                Save Configuration
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}

export default NodeConfigEditor
