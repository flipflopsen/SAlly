import Cable from "./classes/cable";
import Vector2D from "./classes/vector-2d";
import Bus from "./classes/bus";
import ExtGrid from "./classes/ext-grid";
import Trafo from "./classes/trafo";
import Load from "./classes/load";
import Generator from "./classes/generator";
import ElectricElement from "./classes/electric-element";
import StructuredElement from "./classes/structured-element";
import { GrafanaControlComponent } from "../dashboard/grafana-control/grafana-control.component"

export default interface State {
  grafanaControl: GrafanaControlComponent,

  canvas: HTMLCanvasElement,
  timelineDiv: HTMLDivElement,
  backBtn: HTMLButtonElement,
  openInfoboardBtn: HTMLButtonElement,
  timelineSlider: HTMLInputElement,
  selectedRecordText: HTMLOutputElement,

  trafoImg: HTMLImageElement,
  loadImg: HTMLImageElement,
  generatorImg: HTMLImageElement,
  extGridImg: HTMLImageElement,
  busImg: HTMLImageElement,
  switchImg: HTMLImageElement,

  overvoltageImg: HTMLImageElement,
  undervoltageImg: HTMLImageElement,

  OVERALLWIDTH: number,
  OVERALLHEIGHT: number,

  // the one were we gather all the changes before we update the real canvas
  bufferCanvas: HTMLCanvasElement,

  // API of the canvas, called context
  context: CanvasRenderingContext2D,
  bufferContext: CanvasRenderingContext2D,

  // for the animationframe (in case multiple are used)
  animationId: number,
  // keep track of changes due to user mouse position so that the screen can
  // be refreshed accordingly
  userChange: boolean,
  // keep track of redrawing due to scaling changes
  scalingChange: boolean,
  // keep track of changes in the underlying model so that the screen can be
  // refreshed accordingly
  valueChange: boolean,

  // arrays which keep track of all the objects

  // cables are technically electric Components but this extra-array makes it
  // easier to determine draw-order
  electricComponentsArray: ElectricElement[],
  // elements can lay on top of each other and thus multiple elements can be
  // selected with a single click --> Need array
  cablesArray: Cable[],
  // elements can lay on top of each other and thus user can hover over multiple
  // elements at once --> need array
  clickedElementsArray: ElectricElement[],
  hoverElementsArray: ElectricElement[],
  // the last object in clickedElementsArray. Relevant for edit-mode
  clickedElement: ElectricElement | null,

  // user-input variables

  // true if user has mousedown pressed --> important for dragging behavior
  mouseDown: boolean,
  // position of the cursor of the user when he started dragging
  lastDraggingCoor: Vector2D,
  // current mouse position
  mousePos: Vector2D,
  // current mouse position translated to the bigger buffercanvas
  translatedMousePos: Vector2D,
  // says if the user tries to drag an element
  dragsElement: boolean,
 
  keyS: boolean,  // for creating a savefile of the grid
  keyE: boolean,  // for toggelling edit mode
  // triggered by pressing and then releasing "s" in editmode
  saveGridEvent: boolean,
  editMode: boolean,

  // variables for scaling behavoir --> here are just initialization values, they change with user-input!

  // because canvas.style.marginTop is a string, but we need a number
  marginTop: number,
  marginLeft: number,
  // how the actual canvas is scaled relative to bufferCanvas
  scaleWindowWidth: number,
  scaleWindowHeight: number,
  // scales the position of all elements on the canvas
  scaleFactor: number,
  defaultScaleFactor: number,

  // variables for opening another tab
  clickedBtn: boolean,
  lastClickedElement: StructuredElement | null,

  // variables for correctly drawing the grid
  tryToAddChildLaterList: [StructuredElement, StructuredElement][],
  networkConfigFile: Record<string, any> | null,

  // variables for accessing elements & function of the timeline
  myDbase: Record<string, any> | null,

  busDict: Record<string, Bus>,
  extGridDict: Record<string, ExtGrid>,
  loadDict: Record<string, Load>,
  generatorsDict: Record<string, Generator>,
  trafoDict: Record<string, Trafo>,
  lineDict: Record<string, Cable>,
  switchDict: Record<string, Bus>,

  currentFrame: number,

  // dict to find elements per type fast
  elemTypeToArrayDict: {
    line: Record<string, Cable>,
    bus: Record<string, Bus>,
    ext_grid: Record<string, ExtGrid>,
    trafo: Record<string, Trafo>,
    load: Record<string, Load>,
    sgen: Record<string, Generator>,
  },

  // dict to translate the element-types from the dbase to the more readable
  // variables in this program
  unitToAttributeDict: {
    'vm_pu': string,
    'va_degree': string,
    'p_mw': string,
    'q_mvar': string,
    'in_service': string,
    'loading_percent': string,
    'closed': string
  }
}
