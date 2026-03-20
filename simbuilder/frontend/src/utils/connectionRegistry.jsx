/**
 * Frontend connection type registry mapping types to React components
 * Updated to match backend connection types: input, output, monitor
 */
import BaseConnection from '../components/connections/BaseConnection'
import InputConnection from '../components/connections/InputConnection'
import OutputConnection from '../components/connections/OutputConnection'
import MonitorConnection from '../components/connections/MonitorConnection'

export const connectionTypes = {
  input: InputConnection,
  output: OutputConnection,
  monitor: MonitorConnection,
}